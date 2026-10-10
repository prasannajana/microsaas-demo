import type { ReactNode } from 'react';
import { Skeleton, Stat, StatHelpText, StatLabel, StatNumber } from '@chakra-ui/react';
import { GlassCard, type GlassCardProps } from '../ui/GlassCard';

export interface StatCardProps extends Omit<GlassCardProps, 'children'> {
  label: string;
  value: ReactNode;
  helpText?: ReactNode;
  /** Chakra color token for the value, e.g. "green.500". */
  valueColor?: string;
  isLoading?: boolean;
}

/** Single KPI tile: label, big number, optional helper text. */
export function StatCard({ label, value, helpText, valueColor, isLoading = false, ...rest }: StatCardProps) {
  return (
    <GlassCard {...rest}>
      <Stat>
        <StatLabel color="text.muted" fontSize="sm" fontWeight="medium">
          {label}
        </StatLabel>
        <Skeleton isLoaded={!isLoading} mt={1} minH="2.5rem">
          <StatNumber fontSize="3xl" fontWeight="bold" color={valueColor} data-testid="stat-value">
            {value}
          </StatNumber>
        </Skeleton>
        {helpText && (
          <StatHelpText color="text.muted" mb={0}>
            {helpText}
          </StatHelpText>
        )}
      </Stat>
    </GlassCard>
  );
}
