import {
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  Text,
  useToast,
} from '@chakra-ui/react';
import { useNavigate } from 'react-router-dom';
import type { ProjectOut } from '../../types';
import { useDeleteProject } from '../../hooks/useProjects';
import { getErrorMessage } from '../../lib/errors';
import { ActionButton } from './ActionButton';

export interface DeleteProjectModalProps {
  project: ProjectOut;
  isOpen: boolean;
  onClose: () => void;
}

export function DeleteProjectModal({ project, isOpen, onClose }: DeleteProjectModalProps) {
  const toast = useToast();
  const navigate = useNavigate();
  const remove = useDeleteProject();

  const handleDelete = async () => {
    try {
      await remove.mutateAsync(project.id);
      toast({ status: 'success', title: `Deleted ${project.name}` });
      onClose();
      navigate('/projects', { replace: true });
    } catch (err) {
      toast({ status: 'error', title: 'Could not delete project', description: getErrorMessage(err) });
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} isCentered>
      <ModalOverlay backdropFilter="blur(4px)" />
      <ModalContent borderRadius="2xl" mx={4}>
        <ModalHeader>Delete project?</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <Text>
            This permanently deletes <Text as="strong">{project.name}</Text> and all of its scan history. This cannot
            be undone.
          </Text>
        </ModalBody>
        <ModalFooter gap={3}>
          <ActionButton variant="ghost" onClick={onClose}>
            Cancel
          </ActionButton>
          <ActionButton colorScheme="red" onClick={handleDelete} isLoading={remove.isPending}>
            Delete project
          </ActionButton>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
