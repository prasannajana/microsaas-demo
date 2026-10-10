import type { ReactNode } from 'react';
import { MotionBox, type MotionBoxProps } from './motion';

export interface GlassCardProps extends Omit<MotionBoxProps, 'children'> {
  children: ReactNode;
  /** Lift on hover (default true). Disable for static containers such as forms. */
  hoverable?: boolean;
}

export function GlassCard({ children, hoverable = true, ...rest }: GlassCardProps) {
  return (
    <MotionBox
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      whileHover={hoverable ? { y: -4, scale: 1.01 } : undefined}
      p={6}
      borderRadius="card"
      bg="bg.glass"
      backdropFilter="blur(16px)"
      borderWidth="1px"
      borderColor="border.glass"
      boxShadow="glass"
      _hover={hoverable ? { boxShadow: 'glassHover' } : undefined}
      {...rest}
    >
      {children}
    </MotionBox>
  );
}
