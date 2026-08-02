import type {
  AnalyzeCallResponse,
  CallAnalysis,
  ObjectionResponse,
  ScoreBreakdown,
  ScoreCategory,
  ScoreResult,
  Sentiment,
} from '../types/analysis';

const DEFAULT_API_BASE_URL = 'http://localhost:8000';

const SENTIMENTS: readonly Sentiment[] = [
  'positive',
  'neutral',
  'mixed',
  'negative',
];
const SCORE_CATEGORIES: readonly ScoreCategory[] = [
  'Excellent',
  'Good',
  'Needs Improvement',
  'Poor',
];

function getApiBaseUrl(): string {
  const configuredUrl = import.meta.env.VITE_API_BASE_URL?.trim();
  return (configuredUrl || DEFAULT_API_BASE_URL).replace(/\/+$/, '');
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function isStringArray(value: unknown): value is string[] {
  return (
    Array.isArray(value) && value.every((item) => typeof item === 'string')
  );
}

function isIntegerBetween(
  value: unknown,
  minimum: number,
  maximum: number,
): value is number {
  return (
    typeof value === 'number' &&
    Number.isInteger(value) &&
    value >= minimum &&
    value <= maximum
  );
}

function isObjectionResponse(value: unknown): value is ObjectionResponse {
  return (
    isRecord(value) &&
    isNonEmptyString(value.objection) &&
    (typeof value.response === 'string' || value.response === null)
  );
}

function isCallAnalysis(value: unknown): value is CallAnalysis {
  return (
    isRecord(value) &&
    isNonEmptyString(value.summary) &&
    isStringArray(value.customer_needs) &&
    isStringArray(value.questions_asked) &&
    Array.isArray(value.objections) &&
    value.objections.every(isObjectionResponse) &&
    isStringArray(value.follow_up_actions) &&
    typeof value.sentiment === 'string' &&
    SENTIMENTS.includes(value.sentiment as Sentiment) &&
    typeof value.next_step_confirmed === 'boolean' &&
    isIntegerBetween(value.objection_handling_quality, 0, 5) &&
    isIntegerBetween(value.discovery_quality, 0, 5) &&
    isIntegerBetween(value.communication_clarity, 0, 5)
  );
}

function isScoreBreakdown(value: unknown): value is ScoreBreakdown {
  return (
    isRecord(value) &&
    isIntegerBetween(value.discovery, 0, 25) &&
    isIntegerBetween(value.objection_handling, 0, 25) &&
    isIntegerBetween(value.communication_clarity, 0, 20) &&
    isIntegerBetween(value.confirmed_next_step, 0, 20) &&
    isIntegerBetween(value.follow_up_actions, 0, 10)
  );
}

function isScoreResult(value: unknown): value is ScoreResult {
  return (
    isRecord(value) &&
    isIntegerBetween(value.total, 0, 100) &&
    typeof value.category === 'string' &&
    SCORE_CATEGORIES.includes(value.category as ScoreCategory) &&
    isScoreBreakdown(value.breakdown)
  );
}

function isAnalyzeCallResponse(value: unknown): value is AnalyzeCallResponse {
  return (
    isRecord(value) &&
    isNonEmptyString(value.transcript) &&
    isCallAnalysis(value.analysis) &&
    isScoreResult(value.score)
  );
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return (await response.json()) as unknown;
  } catch {
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}.`);
    }

    throw new Error('The server returned an invalid JSON response.');
  }
}

function getErrorDetail(payload: unknown): string | null {
  if (
    isRecord(payload) &&
    typeof payload.detail === 'string' &&
    payload.detail.trim()
  ) {
    return payload.detail;
  }

  return null;
}

export async function analyzeCall(file: File): Promise<AnalyzeCallResponse> {
  const formData = new FormData();
  formData.append('file', file);

  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/api/analyze-call`, {
      method: 'POST',
      body: formData,
    });
  } catch {
    throw new Error(
      'Unable to connect to the analysis service. Check that the backend is running.',
    );
  }

  const payload = await readJson(response);

  if (!response.ok) {
    throw new Error(
      getErrorDetail(payload) ??
        `Request failed with status ${response.status}.`,
    );
  }

  if (!isAnalyzeCallResponse(payload)) {
    throw new Error('The server returned malformed analysis data.');
  }

  return payload;
}
