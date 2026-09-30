import { describe, expect, it } from 'vitest';

import {
  isClientCommand,
  parseCreateCallResponse,
  parseServerEvent,
} from '../src/types/realtime';

const ENVELOPE = {
  protocol_version: 1,
  event_id: 'event-1',
  call_id: 'call-1',
  seq: 1,
  emitted_at: '2026-09-30T08:00:00Z',
};

describe('realtime protocol validation', () => {
  it('parses a known discriminated server event', () => {
    const event = parseServerEvent({
      ...ENVELOPE,
      type: 'call.started',
      payload: {
        state: 'live',
        command_id: 'command-1',
        duplicate: false,
      },
    });

    expect(event?.type).toBe('call.started');
    if (event?.type === 'call.started') {
      expect(event.payload.state).toBe('live');
    }
  });

  it('rejects incompatible versions visibly', () => {
    expect(() =>
      parseServerEvent({
        ...ENVELOPE,
        protocol_version: 2,
        type: 'session.ready',
        payload: { state: 'connecting' },
      }),
    ).toThrow('incompatible protocol version');
  });

  it('rejects malformed payloads', () => {
    expect(() =>
      parseServerEvent({
        ...ENVELOPE,
        type: 'call.started',
        payload: { state: 'ended' },
      }),
    ).toThrow('payload is malformed');
  });

  it('returns null for an unknown optional event type', () => {
    expect(
      parseServerEvent({
        ...ENVELOPE,
        type: 'future.optional-event',
        payload: {},
      }),
    ).toBeNull();
  });

  it('validates call creation responses', () => {
    expect(
      parseCreateCallResponse({
        protocol_version: 1,
        call_id: 'call-1',
        websocket_path: '/ws/calls/call-1',
        state: 'idle',
      }),
    ).toEqual({
      protocol_version: 1,
      call_id: 'call-1',
      websocket_path: '/ws/calls/call-1',
      state: 'idle',
    });
  });

  it('validates client commands and rejects extra start payload data', () => {
    expect(
      isClientCommand({
        protocol_version: 1,
        command_id: 'command-1',
        type: 'start',
        payload: {},
      }),
    ).toBe(true);
    expect(
      isClientCommand({
        protocol_version: 1,
        command_id: 'command-1',
        type: 'start',
        payload: { unexpected: true },
      }),
    ).toBe(false);
  });
});
