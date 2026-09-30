export const PCM_SAMPLE_RATE_HZ = 24_000;
export const PCM_CHANNELS = 1;
export const PCM_FRAME_DURATION_MS = 100;

export function encodePcm16Le(samples: readonly number[]): ArrayBuffer {
  const buffer = new ArrayBuffer(samples.length * 2);
  const view = new DataView(buffer);
  samples.forEach((sample, index) => {
    const clipped = Math.max(-1, Math.min(1, sample));
    const encoded = Math.round(
      clipped < 0 ? clipped * 32_768 : clipped * 32_767,
    );
    view.setInt16(index * 2, encoded, true);
  });
  return buffer;
}

export class ContinuousPcmEncoder {
  private readonly ratio: number;
  private readonly samplesPerFrame: number;
  private sourceSamples: number[] = [];
  private sourcePosition = 0;
  private pendingSamples: number[] = [];
  private totalInputSamples = 0;
  private totalOutputSamples = 0;

  constructor(
    inputSampleRate: number,
    private readonly onFrame: (frame: ArrayBuffer) => void,
    outputSampleRate = PCM_SAMPLE_RATE_HZ,
    frameDurationMs = PCM_FRAME_DURATION_MS,
  ) {
    if (inputSampleRate <= 0 || outputSampleRate <= 0) {
      throw new Error('Audio sample rates must be positive.');
    }
    this.ratio = inputSampleRate / outputSampleRate;
    this.samplesPerFrame = Math.round(
      (outputSampleRate * frameDurationMs) / 1_000,
    );
  }

  push(samples: Float32Array): void {
    if (samples.length === 0) return;
    this.totalInputSamples += samples.length;
    this.sourceSamples.push(...samples);
    this.resample(false);
  }

  flush(): void {
    this.resample(true);
    if (this.pendingSamples.length > 0) {
      this.onFrame(encodePcm16Le(this.pendingSamples));
      this.pendingSamples = [];
    }
    this.sourceSamples = [];
    this.sourcePosition = 0;
  }

  private resample(final: boolean): void {
    const targetTotal = final
      ? Math.round(this.totalInputSamples / this.ratio)
      : Number.POSITIVE_INFINITY;

    while (
      this.sourceSamples.length > 0 &&
      this.totalOutputSamples < targetTotal &&
      (final || this.sourcePosition + 1 < this.sourceSamples.length)
    ) {
      const lowerIndex = Math.floor(this.sourcePosition);
      const upperIndex = Math.min(
        lowerIndex + 1,
        this.sourceSamples.length - 1,
      );
      const fraction = this.sourcePosition - lowerIndex;
      const lower = this.sourceSamples[lowerIndex];
      const upper = this.sourceSamples[upperIndex];
      this.pendingSamples.push(lower + (upper - lower) * fraction);
      this.totalOutputSamples += 1;
      this.sourcePosition += this.ratio;
      this.emitFullFrames();
    }

    const removable = Math.min(
      Math.floor(this.sourcePosition),
      Math.max(0, this.sourceSamples.length - 1),
    );
    if (removable > 0) {
      this.sourceSamples.splice(0, removable);
      this.sourcePosition -= removable;
    }
  }

  private emitFullFrames(): void {
    while (this.pendingSamples.length >= this.samplesPerFrame) {
      const frame = this.pendingSamples.splice(0, this.samplesPerFrame);
      this.onFrame(encodePcm16Le(frame));
    }
  }
}
