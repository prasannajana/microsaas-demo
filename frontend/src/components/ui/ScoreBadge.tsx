import { Badge, type BadgeProps } from '@chakra-ui/react';
import { getScoreColorScheme } from '../../lib/score';

export interface ScoreBadgeProps extends Omit<BadgeProps, 'children' | 'colorScheme'> {
  score: number | null | undefined;
}

/** Score pill: >=80 green, >=50 orange, else red; null/undefined shows "Not scanned". */
export function ScoreBadge({ score, ...rest }: ScoreBadgeProps) {
  const scanned = score !== null && score !== undefined;
  return (
    <Badge
      colorScheme={getScoreColorScheme(score)}
      variant={scanned ? 'solid' : 'subtle'}
      borderRadius="full"
      px={3}
      py={1}
      fontSize="sm"
      data-testid="score-badge"
      aria-label={scanned ? `Score ${score} out of 100` : 'Not scanned'}
      {...rest}
    >
      {scanned ? `${score}/100` : 'Not scanned'}
    </Badge>
  );
}
