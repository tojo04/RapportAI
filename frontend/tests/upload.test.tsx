import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, vi } from 'vitest';

import App from '../src/App';
import { analyzeCall } from '../src/services/api';
import type { AnalyzeCallResponse } from '../src/types/analysis';

vi.mock('../src/services/api', () => ({
  analyzeCall: vi.fn(),
}));

const mockedAnalyzeCall = vi.mocked(analyzeCall);

const successfulResponse: AnalyzeCallResponse = {
  transcript: 'The customer needs a reporting workflow.',
  analysis: {
    summary: 'The salesperson discussed reporting requirements.',
    customer_needs: ['Automated reporting'],
    questions_asked: ['How often do you prepare reports?'],
    objections: [],
    follow_up_actions: ['Schedule a product demo'],
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

function createAudioFile(name = 'sales-call.mp3'): File {
  return new File(['audio content'], name, { type: 'audio/mpeg' });
}

describe('audio upload workflow', () => {
  beforeEach(() => {
    mockedAnalyzeCall.mockReset();
  });

  it('disables analysis when no file is selected', () => {
    render(<App />);

    expect(screen.getByRole('button', { name: 'Analyze Call' })).toBeDisabled();
  });

  it('shows a valid selected file and enables analysis', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.upload(
      screen.getByLabelText('Choose audio file'),
      createAudioFile(),
    );

    expect(screen.getByText('sales-call.mp3')).toBeInTheDocument();
    expect(screen.getByText('1 KB')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Analyze Call' })).toBeEnabled();
  });

  it('rejects files with an unsupported extension', () => {
    render(<App />);

    fireEvent.change(screen.getByLabelText('Choose audio file'), {
      target: {
        files: [new File(['notes'], 'notes.txt', { type: 'text/plain' })],
      },
    });

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Please choose an MP3 or WAV audio file.',
    );
    expect(screen.getByRole('button', { name: 'Analyze Call' })).toBeDisabled();
    expect(mockedAnalyzeCall).not.toHaveBeenCalled();
  });

  it('shows loading state and prevents duplicate submissions', async () => {
    const user = userEvent.setup();
    let resolveRequest: (value: AnalyzeCallResponse) => void = () => undefined;
    mockedAnalyzeCall.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveRequest = resolve;
        }),
    );
    render(<App />);

    await user.upload(
      screen.getByLabelText('Choose audio file'),
      createAudioFile(),
    );
    await user.click(screen.getByRole('button', { name: 'Analyze Call' }));

    expect(screen.getByRole('status')).toHaveTextContent(
      'Transcribing and analyzing your call…',
    );
    expect(
      screen.getByRole('button', { name: 'Analyzing call…' }),
    ).toBeDisabled();
    expect(mockedAnalyzeCall).toHaveBeenCalledTimes(1);

    resolveRequest(successfulResponse);
    expect(
      await screen.findByRole('heading', { name: 'Analysis complete' }),
    ).toBeInTheDocument();
  });

  it('submits the selected file and shows a success placeholder', async () => {
    const user = userEvent.setup();
    const audioFile = createAudioFile('discovery-call.wav');
    mockedAnalyzeCall.mockResolvedValueOnce(successfulResponse);
    render(<App />);

    await user.upload(screen.getByLabelText('Choose audio file'), audioFile);
    await user.click(screen.getByRole('button', { name: 'Analyze Call' }));

    expect(
      await screen.findByRole('heading', { name: 'Analysis complete' }),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Call score: 91/100 · Excellent'),
    ).toBeInTheDocument();
    expect(mockedAnalyzeCall).toHaveBeenCalledWith(audioFile);
  });

  it('shows a user-facing error when the request fails', async () => {
    const user = userEvent.setup();
    mockedAnalyzeCall.mockRejectedValueOnce(new Error('Backend unavailable.'));
    render(<App />);

    await user.upload(
      screen.getByLabelText('Choose audio file'),
      createAudioFile(),
    );
    await user.click(screen.getByRole('button', { name: 'Analyze Call' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Backend unavailable.',
    );
    expect(screen.getByRole('button', { name: 'Analyze Call' })).toBeEnabled();
    expect(
      screen.queryByRole('heading', { name: 'Analysis complete' }),
    ).not.toBeInTheDocument();
  });
});
