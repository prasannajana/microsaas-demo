import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StatCard } from '../../components/dashboard/StatCard';
import { renderWithProviders } from '../test-utils';

describe('StatCard', () => {
  it('renders label, value and help text', () => {
    renderWithProviders(<StatCard label="Projects" value={12} helpText="across your account" />);
    expect(screen.getByText('Projects')).toBeInTheDocument();
    expect(screen.getByTestId('stat-value')).toHaveTextContent('12');
    expect(screen.getByText('across your account')).toBeInTheDocument();
  });

  it('renders string values', () => {
    renderWithProviders(<StatCard label="Failure rate" value="12.5%" />);
    expect(screen.getByTestId('stat-value')).toHaveTextContent('12.5%');
  });
});
