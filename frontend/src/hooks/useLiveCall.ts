import { useCallback, useEffect, useRef, useState } from 'react';

import {
  createPcmCapture,
  PCM_AUDIO_CONFIG,
  type PcmCapture,
} from '../audio/pcmCapture';
import { createLiveCall, getLiveWebSocketUrl } from '../services/realtimeApi';
import {
  parseServerEvent,
  REALTIME_PROTOCOL_VERSION,
  type CallState,
  type CreateCallResponse,
  type StartCommand,
  type StopCommand,
  type TranscriptPayload,
  type SalesEventPayload,
  type CoachSuggestionPayload,
} from '../types/realtime';

const MAX_SOCKET_BUFFERED_BYTES = 1_048_576;
const CONNECTION_TIMEOUT_MS = 10_000;
const STOP_TIMEOUT_MS = 5_000;
const OPEN_SOCKET_STATE = 1;
const CONNECTING_SOCKET_STATE = 0;

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
  createCapture: (
    stream: MediaStream,
    onFrame: (frame: ArrayBuffer) => void,
  ) => Promise<PcmCapture>;
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
  transcript: LiveTranscriptSegment[];
  signals: SalesEventPayload[];
  suggestions: CoachSuggestionPayload[];
  start: () => Promise<void>;
  stop: () => Promise<void>;
}

export interface LiveTranscriptSegment extends TranscriptPayload {
  isFinal: boolean;
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
    createCapture: createPcmCapture,
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
  const [transcript, setTranscript] = useState<LiveTranscriptSegment[]>([]);
  const [signals, setSignals] = useState<SalesEventPayload[]>([]);
  const [suggestions, setSuggestions] = useState<CoachSuggestionPayload[]>([]);

  const mountedRef = useRef(false);
  const statusRef = useRef<CallState>('idle');
  const startingRef = useRef(false);
  const intentionalCloseRef = useRef(false);
  const streamRef = useRef<MediaStream | null>(null);
  const captureRef = useRef<PcmCapture | null>(null);
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
    captureRef.current?.close();
    captureRef.current = null;
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

  const queueFrame = useCallback((frame: ArrayBuffer) => {
    if (frame.byteLength === 0) return;
    sendChainRef.current = sendChainRef.current
      .then(() => {
        const socket = socketRef.current;
        const session = sessionRef.current;
        if (
          socket === null ||
          session === null ||
          socket.readyState !== OPEN_SOCKET_STATE
        ) {
          throw new Error('The live audio connection closed unexpectedly.');
        }
        if (frame.byteLength > session.limits.max_frame_bytes) {
          throw new Error('A microphone frame exceeded the server size limit.');
        }
        if (frame.byteLength % 2 !== 0) {
          throw new Error('A microphone frame was not aligned as 16-bit PCM.');
        }
        if (socket.bufferedAmount > MAX_SOCKET_BUFFERED_BYTES) {
          throw new Error(
            'The live audio connection is congested. The call was stopped.',
          );
        }
        socket.send(frame);
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
      await captureRef.current?.stop();
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
      setTranscript([]);
      setSignals([]);
      setSuggestions([]);
    }

    try {
      const stream = await dependencies.requestMicrophone();
      streamRef.current = stream;
      if (!mountedRef.current) {
        cleanup();
        return;
      }

      const capture = await dependencies.createCapture(stream, queueFrame);
      captureRef.current = capture;

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
                  audio: PCM_AUDIO_CONFIG,
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
              void capture.start().catch((captureError: unknown) => {
                failRef.current(
                  userMessage(captureError, 'The browser microphone failed.'),
                );
              });
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
            case 'transcript.partial':
            case 'transcript.final':
              if (mountedRef.current) {
                setTranscript((current) => {
                  const existing = current.find(
                    (segment) =>
                      segment.segment_id === event.payload.segment_id,
                  );
                  if (
                    existing?.isFinal ||
                    (existing !== undefined &&
                      existing.revision >= event.payload.revision)
                  ) {
                    return current;
                  }
                  const next = current.filter(
                    (segment) =>
                      segment.segment_id !== event.payload.segment_id,
                  );
                  next.push({
                    ...event.payload,
                    isFinal: event.type === 'transcript.final',
                  });
                  return next.sort(
                    (left, right) =>
                      left.order - right.order ||
                      left.segment_id.localeCompare(right.segment_id),
                  );
                });
              }
              break;
            case 'sales.event':
              if (mountedRef.current) {
                setSignals((current) =>
                  current.some(
                    (signal) =>
                      signal.sales_event_id === event.payload.sales_event_id,
                  )
                    ? current
                    : [...current, event.payload],
                );
              }
              break;
            case 'coach.suggestion':
              if (mountedRef.current) {
                setSuggestions((current) =>
                  current.some(
                    (item) => item.suggestion_id === event.payload.suggestion_id,
                  )
                    ? current
                    : [...current, event.payload],
                );
              }
              break;
            case 'call.stopping':
              updateStatus('stopping');
              break;
            case 'call.ended':
              if (!event.payload.transcript_complete && mountedRef.current) {
                setError(
                  'The call ended before transcription fully finalized. The visible transcript may be incomplete.',
                );
              }
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
  }, [beginElapsedTimer, cleanup, dependencies, queueFrame, updateStatus]);

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
    transcript,
    signals,
    suggestions,
    start,
    stop,
  };
}
