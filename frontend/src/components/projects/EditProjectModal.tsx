import { useState, type FormEvent } from 'react';
import {
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  useToast,
  VStack,
} from '@chakra-ui/react';
import type { ProjectOut } from '../../types';
import { useUpdateProject } from '../../hooks/useProjects';
import { getErrorMessage } from '../../lib/errors';
import { AnimatedInput } from '../ui/AnimatedInput';
import { GradientButton } from '../ui/GradientButton';
import { ActionButton } from './ActionButton';
import { getBranchError, getNameError } from './validation';

export interface EditProjectModalProps {
  project: ProjectOut;
  isOpen: boolean;
  onClose: () => void;
}

interface FormErrors {
  name?: string;
  branch?: string;
}

function EditProjectForm({ project, onClose }: Omit<EditProjectModalProps, 'isOpen'>) {
  const toast = useToast();
  const update = useUpdateProject(project.id);
  const [name, setName] = useState(project.name);
  const [branch, setBranch] = useState(project.default_branch ?? '');
  const [errors, setErrors] = useState<FormErrors>({});

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const next: FormErrors = {
      name: getNameError(name) ?? undefined,
      branch: getBranchError(branch) ?? undefined,
    };
    setErrors(next);
    if (next.name || next.branch) return;
    try {
      await update.mutateAsync({ name: name.trim(), default_branch: branch.trim() || undefined });
      toast({ status: 'success', title: 'Project updated' });
      onClose();
    } catch (err) {
      toast({ status: 'error', title: 'Could not update project', description: getErrorMessage(err) });
    }
  };

  return (
    <form onSubmit={handleSubmit} noValidate aria-label="Edit project">
      <ModalBody>
        <VStack spacing={4}>
          <AnimatedInput
            name="edit-name"
            label="Project name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            error={errors.name}
            isRequired
          />
          <AnimatedInput
            name="edit-branch"
            label="Branch"
            placeholder="Default branch"
            value={branch}
            onChange={(e) => setBranch(e.target.value)}
            error={errors.branch}
            helperText="Leave empty to scan the repository's default branch."
          />
        </VStack>
      </ModalBody>
      <ModalFooter gap={3}>
        <ActionButton variant="ghost" onClick={onClose}>
          Cancel
        </ActionButton>
        <GradientButton type="submit" isLoading={update.isPending}>
          Save changes
        </GradientButton>
      </ModalFooter>
    </form>
  );
}

export function EditProjectModal({ project, isOpen, onClose }: EditProjectModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} isCentered>
      <ModalOverlay backdropFilter="blur(4px)" />
      <ModalContent borderRadius="2xl" mx={4}>
        <ModalHeader>Edit project</ModalHeader>
        <ModalCloseButton />
        {isOpen && <EditProjectForm project={project} onClose={onClose} />}
      </ModalContent>
    </Modal>
  );
}
