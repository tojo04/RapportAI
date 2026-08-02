import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { analyzeCall } from '../src/services/api';
import type { AnalyzeCallResponse } from '../src/types/analysis';

const SUCCESS_RESPONSE: AnalyzeCallResponse = {
  transcript: 'A useful transcript.',
  analysis: {
    summary: 'The customer wants automated reporting.',
    customer_needs: ['Automated reports'],
    questions_asked: ['How long does reporting take?'],
    objections: [
      {
        objection: 'The plan may be too expensive.',
        response: 'The salesperson offered a smaller plan.',
      },
    ],
    follow_up_actions: ['Send a proposal'],
    sentiment: 'positive',
    next_step_confirmed: true,
    objection_handling_quality: 4,
    discovery_quality: 5,
    communication_clarity: 4,
  },
  score: {
    total: 91,
    category: 'Excellent',
    breakdown: {
      discovery: 25,
      objection_handling: 20,
      communication_clarity: 16,
      confirmed_next_step: 20,
      follow_up_actions: 10,
    },
  },
};

const fetchMock = vi.fn<typeof fetch>();

function jsonResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response;
}

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock);
  vi.stubEnv('VITE_API_BASE_URL', 'http://api.example.test/');
});

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe('analyzeCall', () => {
  it('returns a validated successful response', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(SUCCESS_RESPONSE));

    const result = await analyzeCall(
      new File(['audio'], 'call.mp3', { type: 'audio/mpeg' }),
    );

    expect(result).toEqual(SUCCESS_RESPONSE);
    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.example.test/api/analyze-call',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('sends the file using the required multipart field name', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(SUCCESS_RESPONSE));
    const file = new File(['audio'], 'call.wav', { type: 'audio/wav' });

    await analyzeCall(file);

    const request = fetchMock.mock.calls[0]?.[1];
    expect(request?.body).toBeInstanceOf(FormData);
    expect((request?.body as FormData).get('file')).toBe(file);
    expect(request?.headers).toBeUndefined();
  });

  it('uses the human-readable FastAPI detail error', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: 'Only MP3 and WAV files are supported.' }, 400),
    );

    await expect(
      analyzeCall(new File(['text'], 'call.txt', { type: 'text/plain' })),
    ).rejects.toThrow('Only MP3 and WAV files are supported.');
  });

  it('reports network failures clearly', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));

    await expect(
      analyzeCall(new File(['audio'], 'call.mp3', { type: 'audio/mpeg' })),
    ).rejects.toThrow('Unable to connect to the analysis service');
  });

  it('rejects successful responses with malformed data', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ ...SUCCESS_RESPONSE, transcript: '' }),
    );

    await expect(
      analyzeCall(new File(['audio'], 'call.mp3', { type: 'audio/mpeg' })),
    ).rejects.toThrow('malformed analysis data');
  });

  it('rejects successful responses containing invalid JSON', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: vi.fn().mockRejectedValue(new SyntaxError('Invalid JSON')),
    } as unknown as Response);

    await expect(
      analyzeCall(new File(['audio'], 'call.wav', { type: 'audio/wav' })),
    ).rejects.toThrow('invalid JSON response');
  });
});
