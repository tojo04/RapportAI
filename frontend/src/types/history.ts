import type { AnalyzeCallResponse } from './analysis';
import type { CoachSuggestionPayload, SalesEventPayload } from './realtime';

export interface CallSummary {
  call_id: string;
  status: string;
  transcript_complete: boolean;
  analysis_status: 'pending' | 'running' | 'completed' | 'failed';
  analysis_version: string | null;
  created_at: string;
  updated_at: string;
}

export interface CallDetail extends CallSummary {
  transcript_segments: Array<{
    segment_id: string;
    order: number;
    text: string;
    language: string | null;
    speaker_role: 'unknown';
  }>;
  sales_events: SalesEventPayload[];
  suggestions: CoachSuggestionPayload[];
  analysis: AnalyzeCallResponse | null;
  analysis_error: string | null;
}
