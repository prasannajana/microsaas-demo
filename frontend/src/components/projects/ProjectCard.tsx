import { Flex, Heading, HStack, LinkOverlay, Tag, Text, VStack } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';
import type { ProjectOut } from '../../types';
import { repoSlugFromUrl } from '../../lib/github';
import { GlassCard } from '../ui/GlassCard';
import { ScoreBadge } from '../ui/ScoreBadge';
import { formatRelativeTime } from './format';

export interface ProjectCardProps {
  project: ProjectOut;
}

export function ProjectCard({ project }: ProjectCardProps) {
  const slug = repoSlugFromUrl(project.repo_url) ?? project.repo_url;
  return (
    <GlassCard position="relative" h="full" data-testid="project-card" whileTap={{ scale: 0.99 }}>
      <VStack align="stretch" spacing={3} h="full">
        <Flex justify="space-between" align="start" gap={3}>
          <VStack align="start" spacing={0} minW={0}>
            <Heading size="sm" noOfLines={1}>
              <LinkOverlay as={RouterLink} to={`/projects/${project.id}`}>
                {project.name}
              </LinkOverlay>
            </Heading>
            <Text fontSize="sm" color="text.muted" noOfLines={1}>
              {slug}
            </Text>
          </VStack>
          <ScoreBadge score={project.latest_score} flexShrink={0} />
        </Flex>
        <HStack justify="space-between" mt="auto" fontSize="sm">
          {project.primary_language ? (
            <Tag size="sm" borderRadius="full" colorScheme="brand" variant="subtle">
              {project.primary_language}
            </Tag>
          ) : (
            <Text color="text.muted">Language unknown</Text>
          )}
          <Text color="text.muted">
            {project.last_scanned_at ? `Scanned ${formatRelativeTime(project.last_scanned_at)}` : 'Never scanned'}
          </Text>
        </HStack>
      </VStack>
    </GlassCard>
  );
}
