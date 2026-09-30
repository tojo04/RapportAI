import {
  ContinuousPcmEncoder,
  PCM_CHANNELS,
  PCM_FRAME_DURATION_MS,
  PCM_SAMPLE_RATE_HZ,
} from './pcmEncoder';

const WORKLET_FLUSH_TIMEOUT_MS = 1_000;

export interface PcmCapture {
  readonly inputSampleRate: number;
  start(): Promise<void>;
  stop(): Promise<void>;
  close(): void;
}

export async function createPcmCapture(
  stream: MediaStream,
  onFrame: (frame: ArrayBuffer) => void,
): Promise<PcmCapture> {
  const context = new AudioContext();
  const encoder = new ContinuousPcmEncoder(context.sampleRate, onFrame);
  await context.audioWorklet.addModule(
    `${import.meta.env.BASE_URL}pcm-capture-worklet.js`,
  );
  const source = context.createMediaStreamSource(stream);
  const worklet = new AudioWorkletNode(context, 'rapportai-pcm-capture');
  const silentOutput = context.createGain();
  silentOutput.gain.value = 0;
  let connected = false;
  let closed = false;

  worklet.port.onmessage = ({ data }: MessageEvent<unknown>) => {
    if (data instanceof Float32Array) encoder.push(data);
  };

  const disconnect = () => {
    if (!connected) return;
    source.disconnect();
    worklet.disconnect();
    silentOutput.disconnect();
    connected = false;
  };

  return {
    inputSampleRate: context.sampleRate,
    async start() {
      if (closed || connected) return;
      source.connect(worklet);
      worklet.connect(silentOutput);
      silentOutput.connect(context.destination);
      connected = true;
      await context.resume();
    },
    async stop() {
      if (closed) return;
      if (connected) {
        await new Promise<void>((resolve) => {
          const timer = window.setTimeout(resolve, WORKLET_FLUSH_TIMEOUT_MS);
          const previous = worklet.port.onmessage;
          worklet.port.onmessage = (event: MessageEvent<unknown>) => {
            if (
              typeof event.data === 'object' &&
              event.data !== null &&
              'type' in event.data &&
              event.data.type === 'flushed'
            ) {
              window.clearTimeout(timer);
              resolve();
              return;
            }
            previous?.call(worklet.port, event);
          };
          worklet.port.postMessage({ type: 'flush' });
        });
      }
      encoder.flush();
      disconnect();
      closed = true;
      worklet.port.onmessage = null;
      void context.close();
    },
    close() {
      if (closed) return;
      disconnect();
      closed = true;
      worklet.port.onmessage = null;
      void context.close();
    },
  };
}

export const PCM_AUDIO_CONFIG = {
  transport: 'pcm_s16le',
  sample_rate_hz: PCM_SAMPLE_RATE_HZ,
  channels: PCM_CHANNELS,
  frame_duration_ms: PCM_FRAME_DURATION_MS,
} as const;
