import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import CallHistory from '../src/components/CallHistory';

const fetchMock = vi.fn<typeof fetch>();

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response;
}

const summary = {
  call_id: 'call-1',
  status: 'ended',
  transcript_complete: true,
  analysis_status: 'failed',
  analysis_version: 'v1',
  created_at: '2026-10-01T10:00:00Z',
  updated_at: '2026-10-01T10:01:00Z',
};

beforeEach(() => vi.stubGlobal('fetch', fetchMock));
afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
});

describe('saved call history', () => {
  it('loads a failed call and schedules an explicit retry', async () => {
    fetchMock
      .mockResolvedValueOnce(
        response({ items: [summary], offset: 0, limit: 20 }),
      )
      .mockResolvedValueOnce(
        response({
          ...summary,
          transcript_segments: [],
          sales_events: [],
          suggestions: [],
          analysis: null,
          analysis_error: 'Provider timeout',
        }),
      )
      .mockResolvedValueOnce(response({ status: 'scheduled' }))
      .mockResolvedValueOnce(
        response({
          ...summary,
          analysis_status: 'running',
          transcript_segments: [],
          sales_events: [],
          suggestions: [],
          analysis: null,
          analysis_error: null,
        }),
      );

    const user = userEvent.setup();
    render(<CallHistory />);
    await user.click(screen.getByRole('button', { name: 'Refresh' }));
    await user.click(
      await screen.findByRole('button', { name: /analysis failed/i }),
    );
    expect(await screen.findByText('Provider timeout')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Retry analysis' }));
    await waitFor(() =>
      expect(screen.getByText(/analysis is running/i)).toBeInTheDocument(),
    );
    expect(fetchMock).toHaveBeenCalledWith('/api/calls/call-1/analysis/retry', {
      method: 'POST',
    });
  });
});
