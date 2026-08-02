import { render, screen, within } from '@testing-library/react';

import AnalysisResults from '../src/components/AnalysisResults';
import ScoreBreakdown from '../src/components/ScoreBreakdown';
import ScoreCard from '../src/components/ScoreCard';
import type { CallAnalysis, ScoreResult } from '../src/types/analysis';

const score: ScoreResult = {
  total: 91,
  category: 'Excellent',
  breakdown: {
    discovery: 25,
    objection_handling: 20,
    communication_clarity: 16,
    confirmed_next_step: 20,
    follow_up_actions: 10,
  },
};

const analysis: CallAnalysis = {
  summary: 'The customer needs a faster reporting workflow.',
  customer_needs: ['Automated weekly reporting'],
  questions_asked: ['How long does reporting take today?'],
  objections: [
    {
      objection: 'The plan may be too expensive.',
      response: null,
    },
  ],
  follow_up_actions: ['Send a proposal'],
  sentiment: 'mixed',
  next_step_confirmed: true,
  objection_handling_quality: 4,
  discovery_quality: 5,
  communication_clarity: 4,
};

describe('result dashboard', () => {
  it('renders the total score and category', () => {
    render(<ScoreCard score={score} />);

    expect(screen.getByLabelText('91 out of 100')).toBeInTheDocument();
    expect(screen.getByText('Excellent')).toBeInTheDocument();
  });

  it('renders every score component and maximum', () => {
    render(<ScoreBreakdown breakdown={score.breakdown} />);

    expect(
      screen.getByLabelText('Discovery: 25 out of 25'),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText('Objection handling: 20 out of 25'),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText('Communication clarity: 16 out of 20'),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText('Confirmed next step: 20 out of 20'),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText('Follow-up actions: 10 out of 10'),
    ).toBeInTheDocument();
  });

  it('renders friendly messages for empty result lists', () => {
    render(
      <AnalysisResults
        analysis={{
          ...analysis,
          customer_needs: [],
          questions_asked: [],
          objections: [],
          follow_up_actions: [],
        }}
        transcript="A short transcript."
      />,
    );

    expect(screen.getAllByText('None identified')).toHaveLength(4);
  });

  it('identifies an objection that received no response', () => {
    render(
      <AnalysisResults analysis={analysis} transcript="A short transcript." />,
    );

    const objections = screen.getByRole('heading', {
      name: 'Objections and responses',
    }).parentElement;
    expect(objections).not.toBeNull();
    expect(
      within(objections as HTMLElement).getByText('No response provided'),
    ).toBeInTheDocument();
  });

  it('renders the transcript in an expandable section', () => {
    render(
      <AnalysisResults
        analysis={analysis}
        transcript="Salesperson: What problem are you solving?"
      />,
    );

    expect(
      screen.getByText('View transcript').closest('details'),
    ).not.toHaveAttribute('open');
    expect(
      screen.getByText('Salesperson: What problem are you solving?'),
    ).toBeInTheDocument();
  });

  it('renders the analyzed sentiment', () => {
    render(
      <AnalysisResults analysis={analysis} transcript="A short transcript." />,
    );

    expect(screen.getByLabelText('Sentiment: mixed')).toHaveTextContent(
      'mixed',
    );
  });
});
