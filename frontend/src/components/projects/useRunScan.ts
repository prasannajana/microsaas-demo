import { useToast } from '@chakra-ui/react';
import { isAxiosError } from 'axios';
import { useStartScan } from '../../hooks/useScans';
import { getErrorMessage } from '../../lib/errors';

/** Wraps useStartScan with toasts that surface 409 (active scan) and 429 (rate limit) messages. */
export function useRunScan(projectId: number) {
  const toast = useToast();
  const start = useStartScan(projectId);

  const run = () => {
    start.mutate(undefined, {
      onSuccess: () => {
        toast({ status: 'info', title: 'Scan started', description: 'We will update this page when it finishes.' });
      },
      onError: (err) => {
        const status = isAxiosError(err) ? err.response?.status : undefined;
        const title =
          status === 409 ? 'A scan is already in progress' : status === 429 ? 'Scan limit reached' : 'Could not start scan';
        toast({ status: status === 409 ? 'warning' : 'error', title, description: getErrorMessage(err) });
      },
    });
  };

  return { run, isPending: start.isPending };
}
