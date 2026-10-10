import { useState, type ChangeEvent, type FormEvent } from 'react';
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, Text, useToast, VStack } from '@chakra-ui/react';
import { isAxiosError } from 'axios';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { ActionButton } from '../components/projects/ActionButton';
import { getBranchError, getNameError } from '../components/projects/validation';
import { AnimatedInput } from '../components/ui/AnimatedInput';
import { GlassCard } from '../components/ui/GlassCard';
import { GradientButton } from '../components/ui/GradientButton';
import { PageWrapper } from '../components/ui/PageWrapper';
import { TextReveal } from '../components/ui/TextReveal';
import { useCreateProject } from '../hooks/useProjects';
import { getErrorMessage } from '../lib/errors';
import { getRepoUrlError, normalizeRepoUrl, repoNameFromUrl } from '../lib/github';

interface FormErrors {
  repoUrl?: string;
  name?: string;
  branch?: string;
}

export default function NewProjectPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const create = useCreateProject();
  const [repoUrl, setRepoUrl] = useState('');
  const [name, setName] = useState('');
  const [nameEdited, setNameEdited] = useState(false);
  const [branch, setBranch] = useState('');
  const [errors, setErrors] = useState<FormErrors>({});

  const handleRepoUrlChange = (event: ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;
    setRepoUrl(value);
    if (!nameEdited) {
      setName(repoNameFromUrl(value) ?? '');
    }
    if (errors.repoUrl) setErrors((prev) => ({ ...prev, repoUrl: undefined }));
  };

  const handleNameChange = (event: ChangeEvent<HTMLInputElement>) => {
    setName(event.target.value);
    setNameEdited(event.target.value.length > 0);
    if (errors.name) setErrors((prev) => ({ ...prev, name: undefined }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const next: FormErrors = {
      repoUrl: getRepoUrlError(repoUrl) ?? undefined,
      name: getNameError(name) ?? undefined,
      branch: getBranchError(branch) ?? undefined,
    };
    setErrors(next);
    if (next.repoUrl || next.name || next.branch) return;

    try {
      const project = await create.mutateAsync({
        name: name.trim(),
        repo_url: normalizeRepoUrl(repoUrl),
        default_branch: branch.trim() || undefined,
      });
      toast({ status: 'success', title: 'Project added', description: 'Run your first scan to get a readiness score.' });
      navigate(`/projects/${project.id}`, { state: { justCreated: true } });
    } catch (err) {
      const status = isAxiosError(err) ? err.response?.status : undefined;
      if (status === 400 || status === 409) {
        setErrors({ repoUrl: getErrorMessage(err) });
      } else {
        toast({ status: 'error', title: 'Could not add project', description: getErrorMessage(err) });
      }
    }
  };

  return (
    <PageWrapper maxW="2xl">
      <Breadcrumb mb={4} fontSize="sm" color="text.muted">
        <BreadcrumbItem>
          <BreadcrumbLink as={RouterLink} to="/projects">
            Projects
          </BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbItem isCurrentPage>
          <BreadcrumbLink>New project</BreadcrumbLink>
        </BreadcrumbItem>
      </Breadcrumb>
      <TextReveal text="Add a project" size="xl" mb={2} />
      <Text color="text.muted" mb={6}>
        Paste a public GitHub repository URL. We will check it for missing essentials like a README, tests, CI and
        deployment config.
      </Text>

      <GlassCard hoverable={false}>
        <form onSubmit={handleSubmit} noValidate aria-label="New project">
          <VStack spacing={5} align="stretch">
            <AnimatedInput
              name="repo_url"
              label="GitHub repository URL"
              placeholder="https://github.com/owner/repo"
              type="url"
              inputMode="url"
              autoComplete="off"
              autoFocus
              value={repoUrl}
              onChange={handleRepoUrlChange}
              onBlur={() => repoUrl.trim() && setErrors((prev) => ({ ...prev, repoUrl: getRepoUrlError(repoUrl) ?? undefined }))}
              error={errors.repoUrl}
              helperText="Only public https://github.com repositories are supported."
              isRequired
            />
            <AnimatedInput
              name="name"
              label="Project name"
              placeholder="my-repo"
              value={name}
              onChange={handleNameChange}
              error={errors.name}
              helperText="Filled in from the repository URL; change it if you like."
              isRequired
            />
            <AnimatedInput
              name="default_branch"
              label="Branch (optional)"
              placeholder="main"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              error={errors.branch}
              helperText="Leave empty to scan the repository's default branch."
            />
            <VStack align="stretch" spacing={3} pt={2}>
              <GradientButton type="submit" size="lg" isLoading={create.isPending} loadingText="Adding…">
                Add project
              </GradientButton>
              <ActionButton variant="ghost" onClick={() => navigate('/projects')}>
                Cancel
              </ActionButton>
            </VStack>
          </VStack>
        </form>
      </GlassCard>
    </PageWrapper>
  );
}
