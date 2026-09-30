import { describe, expect, it, vi } from 'vitest';

import { ContinuousPcmEncoder, encodePcm16Le } from '../src/audio/pcmEncoder';

describe('PCM encoding', () => {
  it('clips known float samples into signed little-endian PCM', () => {
    const bytes = new Uint8Array(encodePcm16Le([-2, -1, 0, 0.5, 1, 2]));
    expect([...bytes]).toEqual([
      0x00, 0x80, 0x00, 0x80, 0x00, 0x00, 0x00, 0x40, 0xff, 0x7f, 0xff, 0x7f,
    ]);
  });

  it.each([44_100, 48_000])(
    'preserves one second duration from %i Hz input',
    (inputRate) => {
      const frames: ArrayBuffer[] = [];
      const encoder = new ContinuousPcmEncoder(inputRate, (frame) =>
        frames.push(frame),
      );
      encoder.push(new Float32Array(inputRate).fill(0.25));
      encoder.flush();

      expect(frames.reduce((total, frame) => total + frame.byteLength, 0)).toBe(
        24_000 * 2,
      );
      expect(
        frames.slice(0, -1).every((frame) => frame.byteLength === 4_800),
      ).toBe(true);
    },
  );

  it('keeps interpolation state across blocks and flushes a short final frame', () => {
    const whole: ArrayBuffer[] = [];
    const split: ArrayBuffer[] = [];
    const samples = Float32Array.from(
      { length: 441 },
      (_, index) => index / 441,
    );
    const wholeEncoder = new ContinuousPcmEncoder(44_100, (frame) =>
      whole.push(frame),
    );
    const splitEncoder = new ContinuousPcmEncoder(44_100, (frame) =>
      split.push(frame),
    );
    wholeEncoder.push(samples);
    wholeEncoder.flush();
    splitEncoder.push(samples.slice(0, 127));
    splitEncoder.push(samples.slice(127, 301));
    splitEncoder.push(samples.slice(301));
    splitEncoder.flush();

    expect(new Uint8Array(split[0])).toEqual(new Uint8Array(whole[0]));
    expect(split[0].byteLength).toBe(480);
  });

  it('does not emit empty frames', () => {
    const onFrame = vi.fn();
    new ContinuousPcmEncoder(48_000, onFrame).flush();
    expect(onFrame).not.toHaveBeenCalled();
  });
});
