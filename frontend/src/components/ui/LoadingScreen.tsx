import { Center, Spinner } from '@chakra-ui/react';

export interface LoadingScreenProps {
  /** Fill the whole viewport (default) or just the parent. */
  fullScreen?: boolean;
}

export function LoadingScreen({ fullScreen = true }: LoadingScreenProps) {
  return (
    <Center minH={fullScreen ? '100vh' : '40vh'} role="status" aria-label="Loading">
      <Spinner size="xl" color="brand.500" thickness="4px" />
    </Center>
  );
}
