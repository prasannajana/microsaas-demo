import type { ReactNode } from 'react';
import { MotionBox, type MotionBoxProps } from './motion';

export interface PageWrapperProps extends Omit<MotionBoxProps, 'children'> {
  children: ReactNode;
}

/** Fades every page in. Use as the outermost element of each page component. */
export function PageWrapper({ children, ...rest }: PageWrapperProps) {
  return (
    <MotionBox
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ duration: 0.3 }}
      w="full"
      maxW="6xl"
      mx="auto"
      px={{ base: 4, md: 8 }}
      py={{ base: 6, md: 10 }}
      {...rest}
    >
      {children}
    </MotionBox>
  );
}
