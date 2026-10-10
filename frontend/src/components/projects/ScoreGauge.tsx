import { CircularProgress, CircularProgressLabel, Text, VStack } from '@chakra-ui/react';
import { getScoreColorScheme } from '../../lib/score';

export interface ScoreGaugeProps {
  score: number | null;
  size?: string;
}

/** Circular 0-100 readiness gauge, colored via lib/score. */
export function ScoreGauge({ score, size = '140px' }: ScoreGaugeProps) {
  const scheme = getScoreColorScheme(score);
  const value = score ?? 0;
  return (
    <VStack spacing={1}>
      <CircularProgress
        value={value}
        size={size}
        thickness="10px"
        color={`${scheme}.400`}
        trackColor="blackAlpha.100"
        capIsRound
        aria-label={score === null ? 'Score not available' : `Readiness score ${score} out of 100`}
        data-testid="score-gauge"
      >
        <CircularProgressLabel fontWeight="bold" fontSize="2xl">
          {score === null ? '—' : score}
        </CircularProgressLabel>
      </CircularProgress>
      <Text fontSize="sm" color="text.muted">
        Readiness score
      </Text>
    </VStack>
  );
}
