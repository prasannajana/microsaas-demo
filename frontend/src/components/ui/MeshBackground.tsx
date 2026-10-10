import { Box } from '@chakra-ui/react';
import { MotionBox } from './motion';

const pulse = {
  animate: { opacity: [0.25, 0.45, 0.25], scale: [1, 1.08, 1] },
  transition: { duration: 8, repeat: Infinity, ease: 'easeInOut' as const },
};

/** Decorative animated gradient background for landing/auth pages. */
export function MeshBackground() {
  return (
    <Box position="fixed" inset={0} zIndex={-1} overflow="hidden" pointerEvents="none" aria-hidden="true">
      <Box position="absolute" inset={0} bgGradient="linear(to-br, brand.50, white, accent.50)" />
      <MotionBox
        position="absolute"
        top="-6rem"
        left="15%"
        w="28rem"
        h="28rem"
        bg="brand.300"
        borderRadius="full"
        filter="blur(80px)"
        animate={pulse.animate}
        transition={pulse.transition}
      />
      <MotionBox
        position="absolute"
        bottom="-6rem"
        right="15%"
        w="28rem"
        h="28rem"
        bg="accent.300"
        borderRadius="full"
        filter="blur(80px)"
        animate={pulse.animate}
        transition={{ ...pulse.transition, delay: 2 }}
      />
    </Box>
  );
}
