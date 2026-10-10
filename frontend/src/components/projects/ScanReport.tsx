import { Code, Flex, Heading, HStack, SimpleGrid, Stack, Text, VStack } from '@chakra-ui/react';
import type { ScanDetail } from '../../types';
import { SEVERITIES } from '../../types';
import { EmptyState } from '../ui/EmptyState';
import { GlassCard } from '../ui/GlassCard';
import { SeverityTag } from '../ui/SeverityTag';
import { FindingsByCategory } from './FindingsByCategory';
import { ScoreGauge } from './ScoreGauge';
import { countBySeverity, formatDateTime, shortSha } from './format';

export interface ScanReportProps {
  scan: ScanDetail;
}

/** Full report for a completed scan: gauge, severity summary and findings grouped by category. */
export function ScanReport({ scan }: ScanReportProps) {
  const counts = countBySeverity(scan.findings);
  const sha = shortSha(scan.commit_sha);
  const clean = scan.findings.length === 0 || scan.score === 100;

  return (
    <VStack align="stretch" spacing={6} data-testid="scan-report">
      <GlassCard hoverable={false}>
        <Stack direction={{ base: 'column', md: 'row' }} spacing={8} align="center">
          <ScoreGauge score={scan.score} />
          <VStack align="stretch" spacing={4} flex="1" w="full">
            <Flex justify="space-between" wrap="wrap" gap={2}>
              <Heading size="md">Scan report</Heading>
              <HStack spacing={3} fontSize="sm" color="text.muted" flexWrap="wrap">
                {sha && (
                  <Text>
                    Commit <Code fontSize="xs">{sha}</Code>
                  </Text>
                )}
                <Text>Completed {formatDateTime(scan.completed_at)}</Text>
              </HStack>
            </Flex>
            <SimpleGrid columns={{ base: 2, sm: 4 }} spacing={3} aria-label="Findings by severity">
              {SEVERITIES.map((severity) => (
                <VStack
                  key={severity}
                  spacing={1}
                  p={3}
                  borderRadius="xl"
                  bg="whiteAlpha.700"
                  borderWidth="1px"
                  borderColor="blackAlpha.100"
                  data-testid={`severity-count-${severity}`}
                >
                  <Text fontSize="2xl" fontWeight="bold">
                    {counts[severity]}
                  </Text>
                  <SeverityTag severity={severity} size="sm" />
                </VStack>
              ))}
            </SimpleGrid>
          </VStack>
        </Stack>
      </GlassCard>

      {clean ? (
        <EmptyState
          icon={<span>🎉</span>}
          title="No missing essentials found 🎉"
          description="This repository has everything we check for: docs, tests, CI, deployment config and more."
        />
      ) : (
        <VStack align="stretch" spacing={3}>
          <Heading size="sm">
            {scan.findings.length} {scan.findings.length === 1 ? 'finding' : 'findings'}
          </Heading>
          <FindingsByCategory findings={scan.findings} />
        </VStack>
      )}
    </VStack>
  );
}
