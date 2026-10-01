import type { CallDetail, CallSummary } from '../types/history';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(
  /\/$/,
  '',
);

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  const body = (await response.json().catch(() => null)) as {
    detail?: string;
  } | null;
  if (!response.ok)
    throw new Error(body?.detail ?? 'Saved calls are unavailable.');
  return body as T;
}

export async function listSavedCalls(): Promise<CallSummary[]> {
  const page = await request<{ items: CallSummary[] }>('/api/calls?limit=20');
  return page.items;
}

export function getSavedCall(callId: string): Promise<CallDetail> {
  return request(`/api/calls/${encodeURIComponent(callId)}`);
}

export function retrySavedAnalysis(
  callId: string,
): Promise<{ status: string }> {
  return request(`/api/calls/${encodeURIComponent(callId)}/analysis/retry`, {
    method: 'POST',
  });
}
