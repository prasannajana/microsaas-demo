import type { ReactNode } from 'react';
import { Box } from '@chakra-ui/react';
import { GlassCard } from '../ui/GlassCard';

/** Glass container with a horizontally scrollable region for wide tables. */
export function AdminTableCard({ children }: { children: ReactNode }) {
  return (
    <GlassCard hoverable={false} p={{ base: 3, md: 6 }}>
      <Box overflowX="auto" w="full">
        {children}
      </Box>
    </GlassCard>
  );
}
