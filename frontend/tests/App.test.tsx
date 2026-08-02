import { render, screen } from '@testing-library/react';

import App from '../src/App';

describe('App', () => {
  it('renders the project title and description', () => {
    render(<App />);

    expect(
      screen.getByRole('heading', { name: 'Sales Call Analyzer' }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /structured insights and an explainable call-quality score/i,
      ),
    ).toBeInTheDocument();
  });
});
