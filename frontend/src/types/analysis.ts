export type Sentiment = 'positive' | 'neutral' | 'mixed' | 'negative';

export type ScoreCategory = 'Excellent' | 'Good' | 'Needs Improvement' | 'Poor';

export interface ObjectionResponse {
  objection: string;
  response: string | null;
}

export interface CallAnalysis {
  summary: string;
  customer_needs: string[];
  questions_asked: string[];
  objections: ObjectionResponse[];
  follow_up_actions: string[];
  sentiment: Sentiment;
  next_step_confirmed: boolean;
  objection_handling_quality: number;
  discovery_quality: number;
  communication_clarity: number;
}

export interface ScoreBreakdown {
  discovery: number;
  objection_handling: number;
  communication_clarity: number;
  confirmed_next_step: number;
  follow_up_actions: number;
}

export interface ScoreResult {
  total: number;
  category: ScoreCategory;
  breakdown: ScoreBreakdown;
}

export interface AnalyzeCallResponse {
  transcript: string;
  analysis: CallAnalysis;
  score: ScoreResult;
}
