class RapportAiPcmCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.port.onmessage = (event) => {
      if (event.data?.type === 'flush') {
        this.port.postMessage({ type: 'flushed' });
      }
    };
  }

  process(inputs) {
    const channels = inputs[0];
    if (!channels || channels.length === 0 || channels[0].length === 0) {
      return true;
    }
    const mono = new Float32Array(channels[0].length);
    for (let channel = 0; channel < channels.length; channel += 1) {
      for (let index = 0; index < mono.length; index += 1) {
        mono[index] += channels[channel][index] / channels.length;
      }
    }
    this.port.postMessage(mono, [mono.buffer]);
    return true;
  }
}

registerProcessor('rapportai-pcm-capture', RapportAiPcmCapture);
