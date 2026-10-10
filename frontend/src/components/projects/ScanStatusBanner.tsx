import { Alert, AlertDescription, AlertIcon, AlertTitle, Box, Progress, VStack } from '@chakra-ui/react';
import type { ScanSummary } from '../../types';
import { ActionButton } from './ActionButton';

export interface ScanStatusBannerProps {
  scan: Pick<ScanSummary, 'status' | 'error_message'>;
  onRetry?: () => void;
  isRetrying?: boolean;
}

/** Banner for queued/running (indeterminate progress) or failed (error + retry) scans. */
export function ScanStatusBanner({ scan, onRetry, isRetrying = false }: ScanStatusBannerProps) {
  if (scan.status === 'queued' || scan.status === 'running') {
    const queued = scan.status === 'queued';
    return (
      <Alert status="info" variant="subtle" borderRadius="xl" flexDirection="column" alignItems="stretch" role="status">
        <Box display="flex" alignItems="center">
          <AlertIcon />
          <VStack align="start" spacing={0}>
            <AlertTitle>{queued ? 'Scan queued' : 'Scanning repository…'}</AlertTitle>
            <AlertDescription fontSize="sm">
              {queued
                ? 'Your scan is waiting to start. This page updates automatically.'
                : 'Cloning and checking for missing essentials. This usually takes a few seconds.'}
            </AlertDescription>
          </VStack>
        </Box>
        <Progress
          mt={3}
          size="xs"
          isIndeterminate
          colorScheme="brand"
          borderRadius="full"
          aria-label={queued ? 'Scan queued' : 'Scan in progress'}
        />
      </Alert>
    );
  }

  if (scan.status === 'failed') {
    return (
      <Alert status="error" variant="subtle" borderRadius="xl" alignItems="center" flexWrap="wrap" gap={3}>
        <AlertIcon />
        <VStack align="start" spacing={0} flex="1">
          <AlertTitle>Scan failed</AlertTitle>
          <AlertDescription fontSize="sm">{scan.error_message ?? 'The scan could not be completed.'}</AlertDescription>
        </VStack>
        {onRetry && (
          <ActionButton size="sm" colorScheme="red" variant="outline" onClick={onRetry} isLoading={isRetrying}>
            Retry scan
          </ActionButton>
        )}
      </Alert>
    );
  }

  return null;
}
