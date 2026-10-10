import type { ReactNode } from 'react';
import { MotionButton, type MotionButtonProps } from './motion';

export interface GradientButtonProps extends Omit<MotionButtonProps, 'children'> {
  children: ReactNode;
}

export function GradientButton({ children, isDisabled, isLoading, ...rest }: GradientButtonProps) {
  const inactive = Boolean(isDisabled) || Boolean(isLoading);
  return (
    <MotionButton
      whileHover={inactive ? undefined : { scale: 1.03, y: -2 }}
      whileTap={inactive ? undefined : { scale: 0.97 }}
      bgGradient="linear(to-r, brand.500, accent.500)"
      color="white"
      px={6}
      borderRadius="full"
      fontWeight="semibold"
      boxShadow="md"
      _hover={{ bgGradient: 'linear(to-r, brand.600, accent.600)', boxShadow: 'lg' }}
      _active={{ bgGradient: 'linear(to-r, brand.700, accent.700)' }}
      isDisabled={isDisabled}
      isLoading={isLoading}
      {...rest}
    >
      {children}
    </MotionButton>
  );
}
