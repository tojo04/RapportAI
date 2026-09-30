import { useCallback, useEffect, useRef, useState } from 'react';

import { createLiveCall, getLiveWebSocketUrl } from '../services/realtimeApi';
import {
  parseServerEvent,
  REALTIME_PROTOCOL_VERSION,
  type CallState,
  type CreateCallResponse,
  type StartCommand,
  type StopCommand,
} from '../types/realtime';

const MEDIA_RECORDER_TIMESLICE_MS = 250;
const MAX_SOCKET_BUFFERED_BYTES = 1_048_576;
const CONNECTION_TIMEOUT_MS = 10_000;
const STOP_TIMEOUT_MS = 5_000;
const RECORDER_STOP_TIMEOUT_MS = 2_000;
const OPEN_SOCKET_STATE = 1;
const CONNECTING_SOCKET_STATE = 0;

export interface MediaRecorderLike {
  readonly mimeType: string;
  readonly state: string;
  ondataavailable: ((event: BlobEvent) => void) | null;
  onerror: ((event: ErrorEvent) => void) | null;
  onstop: ((event: Event) => void) | null;
  start(timeslice?: number): void;
  stop(): void;
}

export interface WebSocketLike {
  binaryType: BinaryType;
  readonly bufferedAmount: number;
  readonly readyState: number;
  onclose: ((event: CloseEvent) => void) | null;
  onerror: ((event: Event) => void) | null;
  onmessage: ((event: MessageEvent<string>) => void) | null;
  onopen: ((event: Event) => void) | null;
  close(code?: number, reason?: string): void;
  send(data: string | ArrayBuffer): void;
}

export interface LiveCallDependencies {
  requestMicrophone: () => Promise<MediaStream>;
  createRecorder: (stream: MediaStream) => MediaRecorderLike;
  createSocket: (url: string) => WebSocketLike;
  createSession: () => Promise<CreateCallResponse>;
  websocketUrl: (path: string) => string;
  commandId: () => string;
}

export interface LiveCallViewModel {
  status: CallState;
  elapsedSeconds: number;
  framesReceived: number;
  bytesReceived: number;
  error: string | null;
  start: () => Promise<void>;
  stop: () => Promise<void>;
}

function chooseRecorderMimeType(): string | undefined {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/ogg;codecs=opus',
    'audio/mp4',
  ];
  return candidates.find((mimeType) => MediaRecorder.isTypeSupported(mimeType));
}

function defaultCreateRecorder(stream: MediaStream): MediaRecorderLike {
  const mimeType = chooseRecorderMimeType();
  const recorder = mimeType
    ? new MediaRecorder(stream, { mimeType })
    : new MediaRecorder(stream);
  if (!recorder.mimeType.toLowerCase().startsWith('audio/')) {
    throw new Error(
      'This browser did not provide a labelled audio recording format.',
    );
  }
  return recorder;
}

function defaultCommandId(): string {
  return typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function defaultDependencies(): LiveCallDependencies {
  return {
    requestMicrophone: () =>
      navigator.mediaDevices.getUserMedia({
        audio: true,
        video: false,
      }),
    createRecorder: defaultCreateRecorder,
    createSocket: (url) => new WebSocket(url),
    createSession: createLiveCall,
    websocketUrl: getLiveWebSocketUrl,
    commandId: defaultCommandId,
  };
}

function userMessage(error: unknown, fallback: string): string {
  if (error instanceof DOMException && error.name === 'NotAllowedError') {
    return 'Microphone permission was denied. Allow access and try again.';
  }
  return error instanceof Error && error.message ? error.message : fallback;
}

export function useLiveCall(
  suppliedDependencies?: LiveCallDependencies,
): LiveCallViewModel {
  const dependenciesRef = useRef<LiveCallDependencies | null>(null);
  if (dependenciesRef.current === null) {
    dependenciesRef.current = suppliedDependencies ?? defaultDependencies();
  }
  const dependencies = dependenciesRef.current;

  const [status, setStatus] = useState<CallState>('idle');
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [framesReceived, setFramesReceived] = useState(0);
  const [bytesReceived, setBytesReceived] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const mountedRef = useRef(false);
  const statusRef = useRef<CallState>('idle');
  const startingRef = useRef(false);
  const intentionalCloseRef = useRef(false);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorderLike | null>(null);
  const socketRef = useRef<WebSocketLike | null>(null);
  const sessionRef = useRef<CreateCallResponse | null>(null);
  const sendChainRef = useRef<Promise<void>>(Promise.resolve());
  const stopPromiseRef = useRef<Promise<void> | null>(null);
  const elapsedTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const durationTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const connectionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stopTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startedAtRef = useRef<number | null>(null);
  const failRef = useRef<(message: string) => void>(() => undefined);
  const stopRef = useRef<() => Promise<void>>(async () => undefined);

  const updateStatus = useCallback((nextStatus: CallState) => {
    statusRef.current = nextStatus;
    if (mountedRef.current) setStatus(nextStatus);
  }, []);

  const clearTimers = useCallback(() => {
    if (elapsedTimerRef.current !== null) {
      clearInterval(elapsedTimerRef.current);
      elapsedTimerRef.current = null;
    }
    for (const timerRef of [
      durationTimerRef,
      connectionTimerRef,
      stopTimerRef,
    ]) {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    }
  }, []);

  const releaseTracks = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  const cleanup = useCallback(() => {
    clearTimers();
    const recorder = recorderRef.current;
    recorderRef.current = null;
    if (recorder !== null) {
      recorder.ondataavailable = null;
      recorder.onerror = null;
      recorder.onstop = null;
      if (recorder.state !== 'inactive') {
        try {
          recorder.stop();
        } catch {
          // The recorder may already be stopping; tracks are still released.
        }
      }
    }
    releaseTracks();

    const socket = socketRef.current;
    socketRef.current = null;
    if (socket !== null) {
      intentionalCloseRef.current = true;
      socket.onopen = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
      if (
        socket.readyState === CONNECTING_SOCKET_STATE ||
        socket.readyState === OPEN_SOCKET_STATE
      ) {
        socket.close(1000, 'Client cleanup');
      }
    }
    sessionRef.current = null;
    startingRef.current = false;
    stopPromiseRef.current = null;
    startedAtRef.current = null;
  }, [clearTimers, releaseTracks]);

  const fail = useCallback(
    (message: string) => {
      if (mountedRef.current) setError(message);
      updateStatus('interrupted');
      cleanup();
    },
    [cleanup, updateStatus],
  );
  failRef.current = fail;

  const queueBlob = useCallback((blob: Blob) => {
    if (blob.size === 0) return;
    sendChainRef.current = sendChainRef.current
      .then(async () => {
        const socket = socketRef.current;
        const session = sessionRef.current;
        if (
          socket === null ||
          session === null ||
          socket.readyState !== OPEN_SOCKET_STATE
        ) {
          throw new Error('The live audio connection closed unexpectedly.');
        }
        if (blob.size > session.limits.max_frame_bytes) {
          throw new Error('A microphone frame exceeded the server size limit.');
        }
        if (socket.bufferedAmount > MAX_SOCKET_BUFFERED_BYTES) {
          throw new Error(
            'The live audio connection is congested. The call was stopped.',
          );
        }
        const buffer = await blob.arrayBuffer();
        if (socket.readyState !== OPEN_SOCKET_STATE) {
          throw new Error('The live audio connection closed unexpectedly.');
        }
        socket.send(buffer);
      })
      .catch((sendError: unknown) => {
        failRef.current(
          userMessage(sendError, 'The microphone frame could not be sent.'),
        );
      });
  }, []);

  const beginElapsedTimer = useCallback((maximumSeconds: number) => {
    startedAtRef.current = Date.now();
    if (mountedRef.current) setElapsedSeconds(0);
    elapsedTimerRef.current = setInterval(() => {
      if (startedAtRef.current !== null && mountedRef.current) {
        setElapsedSeconds(
          Math.floor((Date.now() - startedAtRef.current) / 1_000),
        );
      }
    }, 1_000);
    durationTimerRef.current = setTimeout(() => {
      void stopRef.current();
    }, maximumSeconds * 1_000);
  }, []);

  const stop = useCallback(async (): Promise<void> => {
    if (stopPromiseRef.current !== null) return stopPromiseRef.current;
    if (!['connecting', 'live'].includes(statusRef.current)) return;

    const operation = (async () => {
      updateStatus('stopping');
      clearTimers();
      const recorder = recorderRef.current;
      if (recorder !== null && recorder.state !== 'inactive') {
        await Promise.race([
          new Promise<void>((resolve) => {
            recorder.onstop = () => resolve();
            recorder.stop();
          }),
          new Promise<void>((resolve) => {
            setTimeout(resolve, RECORDER_STOP_TIMEOUT_MS);
          }),
        ]);
      }
      await sendChainRef.current;
      releaseTracks();

      const socket = socketRef.current;
      if (socket === null || socket.readyState !== OPEN_SOCKET_STATE) {
        failRef.current(
          'The live connection closed before the call could stop.',
        );
        return;
      }
      const command: StopCommand = {
        protocol_version: REALTIME_PROTOCOL_VERSION,
        command_id: dependencies.commandId(),
        type: 'stop',
        payload: {},
      };
      socket.send(JSON.stringify(command));
      stopTimerRef.current = setTimeout(() => {
        failRef.current('The server did not finish stopping the call in time.');
      }, STOP_TIMEOUT_MS);
    })();
    stopPromiseRef.current = operation;
    return operation;
  }, [clearTimers, dependencies, releaseTracks, updateStatus]);
  stopRef.current = stop;

  const start = useCallback(async (): Promise<void> => {
    if (
      startingRef.current ||
      ['connecting', 'live', 'stopping'].includes(statusRef.current)
    ) {
      return;
    }

    cleanup();
    intentionalCloseRef.current = false;
    startingRef.current = true;
    sendChainRef.current = Promise.resolve();
    updateStatus('connecting');
    if (mountedRef.current) {
      setError(null);
      setElapsedSeconds(0);
      setFramesReceived(0);
      setBytesReceived(0);
    }

    try {
      const stream = await dependencies.requestMicrophone();
      streamRef.current = stream;
      if (!mountedRef.current) {
        cleanup();
        return;
      }

      const recorder = dependencies.createRecorder(stream);
      if (!recorder.mimeType.toLowerCase().startsWith('audio/')) {
        throw new Error('The browser returned an unknown microphone encoding.');
      }
      recorderRef.current = recorder;
      recorder.ondataavailable = ({ data }) => queueBlob(data);
      recorder.onerror = () => {
        failRef.current('The browser microphone recorder failed.');
      };

      const session = await dependencies.createSession();
      sessionRef.current = session;
      if (!mountedRef.current) {
        cleanup();
        return;
      }

      const socket = dependencies.createSocket(
        dependencies.websocketUrl(session.websocket_path),
      );
      socketRef.current = socket;
      socket.binaryType = 'arraybuffer';
      socket.onopen = () => undefined;
      socket.onerror = () => {
        failRef.current('The live WebSocket connection failed.');
      };
      socket.onclose = () => {
        if (!intentionalCloseRef.current && statusRef.current !== 'ended') {
          failRef.current('The live connection was lost. Start a new call.');
        }
      };
      socket.onmessage = ({ data }) => {
        try {
          const event = parseServerEvent(JSON.parse(data) as unknown);
          if (event === null) return;
          if (event.call_id !== session.call_id) {
            throw new Error('The server returned an event for another call.');
          }

          switch (event.type) {
            case 'session.ready': {
              const command: StartCommand = {
                protocol_version: REALTIME_PROTOCOL_VERSION,
                command_id: dependencies.commandId(),
                type: 'start',
                payload: {
                  audio: {
                    transport: 'media_recorder',
                    mime_type: recorder.mimeType,
                    timeslice_ms: MEDIA_RECORDER_TIMESLICE_MS,
                  },
                },
              };
              socket.send(JSON.stringify(command));
              break;
            }
            case 'call.started':
              if (connectionTimerRef.current !== null) {
                clearTimeout(connectionTimerRef.current);
                connectionTimerRef.current = null;
              }
              if (recorder.state === 'inactive') {
                recorder.start(MEDIA_RECORDER_TIMESLICE_MS);
              }
              startingRef.current = false;
              updateStatus('live');
              beginElapsedTimer(session.limits.max_call_seconds);
              break;
            case 'audio.ack':
              if (mountedRef.current) {
                setFramesReceived(event.payload.frames_received);
                setBytesReceived(event.payload.bytes_received);
              }
              break;
            case 'call.stopping':
              updateStatus('stopping');
              break;
            case 'call.ended':
              updateStatus(event.payload.state);
              cleanup();
              break;
            case 'error':
              if (mountedRef.current) setError(event.payload.message);
              if (event.payload.code === 'call_duration_exceeded') {
                updateStatus('stopping');
              } else if (!event.payload.recoverable) {
                failRef.current(event.payload.message);
              }
              break;
          }
        } catch (eventError: unknown) {
          failRef.current(
            userMessage(eventError, 'The server sent an invalid live event.'),
          );
        }
      };

      connectionTimerRef.current = setTimeout(() => {
        failRef.current('The live call did not connect in time.');
      }, CONNECTION_TIMEOUT_MS);
    } catch (startError: unknown) {
      if (mountedRef.current) {
        setError(
          userMessage(startError, 'The live call could not be started.'),
        );
      }
      updateStatus('failed');
      cleanup();
    }
  }, [beginElapsedTimer, cleanup, dependencies, queueBlob, updateStatus]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      cleanup();
    };
  }, [cleanup]);

  return {
    status,
    elapsedSeconds,
    framesReceived,
    bytesReceived,
    error,
    start,
    stop,
  };
}
