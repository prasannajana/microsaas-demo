import { Code, HStack, Text, VStack } from '@chakra-ui/react';
import type { FindingOut } from '../../types';
import { GlassCard } from '../ui/GlassCard';
import { SeverityTag } from '../ui/SeverityTag';

export interface FindingCardProps {
  finding: FindingOut;
}

export function FindingCard({ finding }: FindingCardProps) {
  return (
    <GlassCard p={4} data-testid="finding-card" aria-label={`${finding.severity} finding: ${finding.title}`}>
      <VStack align="stretch" spacing={2}>
        <HStack spacing={3} align="center" flexWrap="wrap">
          <SeverityTag severity={finding.severity} />
          <Text fontWeight="semibold">{finding.title}</Text>
        </HStack>
        <Text color="text.muted" fontSize="sm">
          {finding.recommendation}
        </Text>
        {finding.file_path && (
          <Text fontSize="sm">
            File: <Code fontSize="xs">{finding.file_path}</Code>
          </Text>
        )}
      </VStack>
    </GlassCard>
  );
}
