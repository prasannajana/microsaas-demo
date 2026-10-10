import { Flex, Heading, Skeleton, Stack, Text } from '@chakra-ui/react';
import type { CommonFinding } from '../../types';
import { AnimatedList } from '../ui/AnimatedList';
import { GlassCard } from '../ui/GlassCard';
import { MotionBox } from '../ui/motion';
import { SeverityTag } from '../ui/SeverityTag';

export interface CommonFindingsListProps {
  findings: CommonFinding[] | undefined;
  isLoading?: boolean;
}

/** Most frequent findings across the user's projects. */
export function CommonFindingsList({ findings, isLoading = false }: CommonFindingsListProps) {
  return (
    <GlassCard hoverable={false} h="full">
      <Heading size="md" mb={4}>
        Common findings
      </Heading>
      {isLoading ? (
        <Stack spacing={3}>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} h="3rem" borderRadius="lg" />
          ))}
        </Stack>
      ) : !findings || findings.length === 0 ? (
        <Text color="text.muted">No open findings. Nice work!</Text>
      ) : (
        <AnimatedList
          items={findings}
          getKey={(f) => f.check_id}
          gap={2}
          renderItem={(f) => (
            <MotionBox
              whileHover={{ x: 4 }}
              p={3}
              borderRadius="lg"
              borderWidth="1px"
              borderColor="border.glass"
              _hover={{ bg: 'blackAlpha.50' }}
            >
              <Flex justify="space-between" align="center" gap={3}>
                <Stack spacing={1} minW={0}>
                  <Text fontWeight="medium" noOfLines={2}>
                    {f.title}
                  </Text>
                  <Text fontSize="sm" color="text.muted">
                    in {f.count} project{f.count === 1 ? '' : 's'}
                  </Text>
                </Stack>
                <SeverityTag severity={f.severity} flexShrink={0} />
              </Flex>
            </MotionBox>
          )}
        />
      )}
    </GlassCard>
  );
}
