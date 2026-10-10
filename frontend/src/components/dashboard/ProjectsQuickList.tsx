import { Link as RouterLink } from 'react-router-dom';
import { Flex, Heading, Link, Skeleton, Stack, Text } from '@chakra-ui/react';
import type { ProjectOut } from '../../types';
import { AnimatedList } from '../ui/AnimatedList';
import { GlassCard } from '../ui/GlassCard';
import { MotionBox } from '../ui/motion';
import { ScoreBadge } from '../ui/ScoreBadge';

export interface ProjectsQuickListProps {
  projects: ProjectOut[] | undefined;
  total?: number;
  isLoading?: boolean;
}

/** Compact list of the user's projects with their latest score. */
export function ProjectsQuickList({ projects, total, isLoading = false }: ProjectsQuickListProps) {
  return (
    <GlassCard hoverable={false} h="full">
      <Flex justify="space-between" align="center" mb={4}>
        <Heading size="md">Your projects</Heading>
        <Link as={RouterLink} to="/projects" color="brand.500" fontSize="sm" fontWeight="semibold">
          View all{total !== undefined ? ` (${total})` : ''}
        </Link>
      </Flex>
      {isLoading ? (
        <Stack spacing={3}>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} h="3rem" borderRadius="lg" />
          ))}
        </Stack>
      ) : !projects || projects.length === 0 ? (
        <Text color="text.muted">No projects yet.</Text>
      ) : (
        <AnimatedList
          items={projects}
          getKey={(p) => p.id}
          gap={2}
          renderItem={(p) => (
            <MotionBox whileHover={{ x: 4 }} whileTap={{ scale: 0.98 }}>
              <Link
                as={RouterLink}
                to={`/projects/${p.id}`}
                display="block"
                p={3}
                borderRadius="lg"
                borderWidth="1px"
                borderColor="border.glass"
                _hover={{ bg: 'blackAlpha.50', textDecoration: 'none' }}
              >
              <Flex justify="space-between" align="center" gap={3}>
                <Stack spacing={0} minW={0}>
                  <Text fontWeight="medium" noOfLines={1}>
                    {p.name}
                  </Text>
                  <Text fontSize="sm" color="text.muted" noOfLines={1}>
                    {p.last_scanned_at
                      ? `Scanned ${new Date(p.last_scanned_at).toLocaleDateString()}`
                      : 'Never scanned'}
                  </Text>
                </Stack>
                <ScoreBadge score={p.latest_score} flexShrink={0} />
              </Flex>
              </Link>
            </MotionBox>
          )}
        />
      )}
    </GlassCard>
  );
}
