import { useState } from 'react';
import { Alert, AlertIcon, Flex, Text, VStack } from '@chakra-ui/react';
import { useNavigate } from 'react-router-dom';
import { ProjectCard } from '../components/projects/ProjectCard';
import { Pagination } from '../components/projects/Pagination';
import { AnimatedList } from '../components/ui/AnimatedList';
import { EmptyState } from '../components/ui/EmptyState';
import { GradientButton } from '../components/ui/GradientButton';
import { LoadingScreen } from '../components/ui/LoadingScreen';
import { PageWrapper } from '../components/ui/PageWrapper';
import { TextReveal } from '../components/ui/TextReveal';
import { PROJECTS_PAGE_SIZE, useProjects } from '../hooks/useProjects';
import { getErrorMessage } from '../lib/errors';

export default function ProjectsListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, error } = useProjects(page, PROJECTS_PAGE_SIZE);
  const goToNew = () => navigate('/projects/new');

  return (
    <PageWrapper>
      <Flex justify="space-between" align={{ base: 'start', sm: 'center' }} direction={{ base: 'column', sm: 'row' }} gap={4} mb={8}>
        <VStack align="start" spacing={1}>
          <TextReveal text="Projects" size="xl" />
          <Text color="text.muted">GitHub repositories you are tracking and their readiness scores.</Text>
        </VStack>
        <GradientButton onClick={goToNew}>Add project</GradientButton>
      </Flex>

      {isLoading ? (
        <LoadingScreen fullScreen={false} />
      ) : isError ? (
        <Alert status="error" borderRadius="xl">
          <AlertIcon />
          {getErrorMessage(error, 'Could not load projects.')}
        </Alert>
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={<span>📦</span>}
          title="No projects yet"
          description="Add a public GitHub repository to see what it is missing and get a 0-100 readiness score."
          action={<GradientButton onClick={goToNew}>Add your first project</GradientButton>}
        />
      ) : (
        <VStack align="stretch" spacing={8}>
          <AnimatedList
            items={data.items}
            getKey={(p) => p.id}
            renderItem={(p) => <ProjectCard project={p} />}
            display="grid"
            gridTemplateColumns={{ base: '1fr', md: 'repeat(2, 1fr)', lg: 'repeat(3, 1fr)' }}
            gap={5}
          />
          <Pagination page={data.page} size={data.size} total={data.total} onChange={setPage} />
        </VStack>
      )}
    </PageWrapper>
  );
}
