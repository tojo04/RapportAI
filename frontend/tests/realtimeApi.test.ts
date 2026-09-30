import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createLiveCall,
  getLiveWebSocketUrl,
} from '../src/services/realtimeApi';

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock);
  vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.test/');
});

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe('realtime API client', () => {
  it('creates and validates a live-call session', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: vi.fn().mockResolvedValue({
        protocol_version: 1,
        call_id: 'call-1',
        websocket_path: '/ws/calls/call-1',
        state: 'idle',
        limits: {
          max_call_seconds: 1_800,
          max_frame_bytes: 262_144,
          ack_every_frames: 4,
        },
      }),
    } as unknown as Response);

    const session = await createLiveCall();

    expect(session.call_id).toBe('call-1');
    expect(fetchMock).toHaveBeenCalledWith(
      'https://api.example.test/api/calls',
      { method: 'POST' },
    );
  });

  it('constructs a secure WebSocket URL from an HTTPS API URL', () => {
    expect(getLiveWebSocketUrl('/ws/calls/call-1')).toBe(
      'wss://api.example.test/ws/calls/call-1',
    );
  });

  it('surfaces a FastAPI error detail', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: vi.fn().mockResolvedValue({
        detail: 'The live-call capacity has been reached.',
      }),
    } as unknown as Response);

    await expect(createLiveCall()).rejects.toThrow('capacity has been reached');
  });
});
