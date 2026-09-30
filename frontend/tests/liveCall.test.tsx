import { StrictMode } from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import {
  useLiveCall,
  type LiveCallDependencies,
  type MediaRecorderLike,
  type WebSocketLike,
} from '../src/hooks/useLiveCall';
import type { CreateCallResponse } from '../src/types/realtime';

const SESSION: CreateCallResponse = {
  protocol_version: 1,
  call_id: 'call-1',
  websocket_path: '/ws/calls/call-1',
  state: 'idle',
  limits: {
    max_call_seconds: 1_800,
    max_frame_bytes: 262_144,
    ack_every_frames: 4,
  },
};

function serverEvent(
  type: string,
  payload: Record<string, unknown>,
  seq = 1,
): string {
  return JSON.stringify({
    protocol_version: 1,
    event_id: `event-${seq}`,
    call_id: 'call-1',
    seq,
    type,
    emitted_at: '2026-09-30T08:00:00Z',
    payload,
  });
}

function audioBlob(size = 5): Blob {
  return {
    size,
    arrayBuffer: vi.fn().mockResolvedValue(new ArrayBuffer(size)),
  } as unknown as Blob;
}

class FakeRecorder implements MediaRecorderLike {
  readonly mimeType = 'audio/webm;codecs=opus';
  state = 'inactive';
  ondataavailable: ((event: BlobEvent) => void) | null = null;
  onerror: ((event: ErrorEvent) => void) | null = null;
  onstop: ((event: Event) => void) | null = null;
  readonly start = vi.fn((timeslice?: number) => {
    void timeslice;
    this.state = 'recording';
  });
  readonly stop = vi.fn(() => {
    if (this.state === 'inactive') return;
    this.state = 'inactive';
    this.ondataavailable?.({ data: audioBlob(3) } as BlobEvent);
    this.onstop?.(new Event('stop'));
  });

  emit(blob = audioBlob()): void {
    this.ondataavailable?.({ data: blob } as BlobEvent);
  }
}

class FakeSocket implements WebSocketLike {
  binaryType: BinaryType = 'blob';
  bufferedAmount = 0;
  readyState = 0;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onopen: ((event: Event) => void) | null = null;
  readonly sent: Array<string | ArrayBuffer> = [];
  readonly close = vi.fn((code?: number, reason?: string) => {
    void code;
    void reason;
    this.readyState = 3;
    this.onclose?.({ code: code ?? 1000 } as CloseEvent);
  });

  send(data: string | ArrayBuffer): void {
    this.sent.push(data);
  }

  open(): void {
    this.readyState = 1;
    this.onopen?.(new Event('open'));
  }

  receive(data: string): void {
    this.onmessage?.({ data } as MessageEvent<string>);
  }

  disconnect(): void {
    this.readyState = 3;
    this.onclose?.({ code: 1006 } as CloseEvent);
  }
}

function setup(overrides: Partial<LiveCallDependencies> = {}) {
  const track = { stop: vi.fn() };
  const stream = {
    getTracks: () => [track],
  } as unknown as MediaStream;
  const recorder = new FakeRecorder();
  const socket = new FakeSocket();
  let commandNumber = 0;
  const dependencies: LiveCallDependencies = {
    requestMicrophone: vi.fn().mockResolvedValue(stream),
    createRecorder: vi.fn().mockReturnValue(recorder),
    createSocket: vi.fn().mockReturnValue(socket),
    createSession: vi.fn().mockResolvedValue(SESSION),
    websocketUrl: vi.fn().mockReturnValue('ws://api.test/ws/calls/call-1'),
    commandId: vi.fn(() => `command-${++commandNumber}`),
    ...overrides,
  };
  return { dependencies, recorder, socket, track };
}

async function reachLiveState(
  dependencies: LiveCallDependencies,
  socket: FakeSocket,
) {
  const hook = renderHook(() => useLiveCall(dependencies));
  await act(async () => {
    await hook.result.current.start();
  });
  act(() => {
    socket.open();
    socket.receive(serverEvent('session.ready', { state: 'connecting' }, 1));
  });
  act(() => {
    socket.receive(
      serverEvent(
        'call.started',
        { state: 'live', command_id: 'command-1', duplicate: false },
        2,
      ),
    );
  });
  return hook;
}

describe('useLiveCall', () => {
  it('streams labelled blobs, renders acknowledgements, and flushes before stop', async () => {
    const { dependencies, recorder, socket, track } = setup();
    const hook = await reachLiveState(dependencies, socket);

    expect(hook.result.current.status).toBe('live');
    expect(recorder.start).toHaveBeenCalledWith(250);
    const startCommand = JSON.parse(socket.sent[0] as string) as {
      payload: { audio: { mime_type: string; transport: string } };
    };
    expect(startCommand.payload.audio).toEqual(
      expect.objectContaining({
        transport: 'media_recorder',
        mime_type: 'audio/webm;codecs=opus',
      }),
    );

    act(() => recorder.emit(audioBlob(5)));
    await waitFor(() => {
      expect(socket.sent.some((item) => item instanceof ArrayBuffer)).toBe(
        true,
      );
    });
    act(() => {
      socket.receive(
        serverEvent('audio.ack', { frames_received: 4, bytes_received: 20 }, 3),
      );
    });
    expect(hook.result.current.framesReceived).toBe(4);
    expect(hook.result.current.bytesReceived).toBe(20);

    await act(async () => {
      await hook.result.current.stop();
    });
    expect(track.stop).toHaveBeenCalledTimes(1);
    const lastSent = socket.sent.at(-1);
    expect(typeof lastSent).toBe('string');
    expect(JSON.parse(lastSent as string).type).toBe('stop');

    act(() => {
      socket.receive(
        serverEvent(
          'call.ended',
          {
            state: 'ended',
            command_id: 'command-2',
            duplicate: false,
            transcript_complete: true,
          },
          4,
        ),
      );
    });
    expect(hook.result.current.status).toBe('ended');
    expect(socket.close).toHaveBeenCalled();
  });

  it('releases the microphone when permission or startup fails', async () => {
    const permissionError = new DOMException('Denied', 'NotAllowedError');
    const { dependencies, track } = setup({
      requestMicrophone: vi.fn().mockRejectedValue(permissionError),
    });
    const hook = renderHook(() => useLiveCall(dependencies));

    await act(async () => {
      await hook.result.current.start();
    });

    expect(hook.result.current.status).toBe('failed');
    expect(hook.result.current.error).toMatch(/permission was denied/i);
    expect(track.stop).not.toHaveBeenCalled();
  });

  it('releases capture and reports network loss', async () => {
    const { dependencies, socket, track } = setup();
    const hook = await reachLiveState(dependencies, socket);

    act(() => socket.disconnect());

    expect(hook.result.current.status).toBe('interrupted');
    expect(hook.result.current.error).toMatch(/connection was lost/i);
    expect(track.stop).toHaveBeenCalledTimes(1);
  });

  it('terminates instead of buffering unbounded audio', async () => {
    const { dependencies, recorder, socket, track } = setup();
    const hook = await reachLiveState(dependencies, socket);
    socket.bufferedAmount = 1_048_577;

    act(() => recorder.emit(audioBlob()));

    await waitFor(() => {
      expect(hook.result.current.status).toBe('interrupted');
    });
    expect(hook.result.current.error).toMatch(/congested/i);
    expect(track.stop).toHaveBeenCalledTimes(1);
  });

  it('prevents duplicate capture in StrictMode and cleans up on unmount', async () => {
    const { dependencies, socket, track } = setup();
    const hook = renderHook(() => useLiveCall(dependencies), {
      wrapper: StrictMode,
    });

    await act(async () => {
      await Promise.all([
        hook.result.current.start(),
        hook.result.current.start(),
      ]);
    });
    expect(dependencies.requestMicrophone).toHaveBeenCalledTimes(1);
    act(() => {
      socket.open();
      socket.receive(serverEvent('session.ready', { state: 'connecting' }, 1));
      socket.receive(
        serverEvent(
          'call.started',
          { state: 'live', command_id: 'command-1', duplicate: false },
          2,
        ),
      );
    });

    hook.unmount();

    expect(track.stop).toHaveBeenCalledTimes(1);
    expect(socket.close).toHaveBeenCalledTimes(1);
  });
});
