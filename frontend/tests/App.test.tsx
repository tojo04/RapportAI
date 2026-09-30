import { render, screen } from '@testing-library/react';

import App from '../src/App';

describe('App', () => {
  it('renders the project title and description', () => {
    render(<App />);

    expect(
      screen.getByRole('heading', { name: 'RapportAI' }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /structured insights and an explainable call-quality score/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Start Live Call' }),
    ).toBeEnabled();
    expect(
      screen.getByRole('button', { name: 'Stop Live Call' }),
    ).toBeDisabled();
  });
});
