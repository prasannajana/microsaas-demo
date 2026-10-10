import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ScoreBadge } from '../components/ui/ScoreBadge';
import { getScoreColorScheme } from '../lib/score';
import { renderWithProviders } from './test-utils';

describe('ScoreBadge', () => {
  it('renders the score out of 100', () => {
    renderWithProviders(<ScoreBadge score={85} />);
    expect(screen.getByTestId('score-badge')).toHaveTextContent('85/100');
  });

  it('renders "Not scanned" for a null score', () => {
    renderWithProviders(<ScoreBadge score={null} />);
    expect(screen.getByTestId('score-badge')).toHaveTextContent('Not scanned');
  });

  it('maps scores to color schemes', () => {
    expect(getScoreColorScheme(80)).toBe('green');
    expect(getScoreColorScheme(79)).toBe('orange');
    expect(getScoreColorScheme(50)).toBe('orange');
    expect(getScoreColorScheme(49)).toBe('red');
    expect(getScoreColorScheme(null)).toBe('gray');
  });
});
