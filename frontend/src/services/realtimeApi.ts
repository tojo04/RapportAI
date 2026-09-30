import {
  parseCreateCallResponse,
  type CreateCallResponse,
} from '../types/realtime';

const DEFAULT_API_BASE_URL = 'http://localhost:8000';

function getApiBaseUrl(): string {
  const configuredUrl = import.meta.env.VITE_API_BASE_URL?.trim();
  return (configuredUrl || DEFAULT_API_BASE_URL).replace(/\/+$/, '');
}

export async function createLiveCall(): Promise<CreateCallResponse> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/api/calls`, {
      method: 'POST',
    });
  } catch {
    throw new Error(
      'Unable to connect to the live-call service. Check that the backend is running.',
    );
  }

  let payload: unknown;
  try {
    payload = (await response.json()) as unknown;
  } catch {
    throw new Error('The live-call service returned invalid JSON.');
  }

  if (!response.ok) {
    const detail =
      typeof payload === 'object' &&
      payload !== null &&
      'detail' in payload &&
      typeof payload.detail === 'string'
        ? payload.detail
        : `Request failed with status ${response.status}.`;
    throw new Error(detail);
  }

  return parseCreateCallResponse(payload);
}

export function getLiveWebSocketUrl(path: string): string {
  const apiUrl = new URL(getApiBaseUrl());
  apiUrl.protocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  return new URL(path, apiUrl).toString();
}
