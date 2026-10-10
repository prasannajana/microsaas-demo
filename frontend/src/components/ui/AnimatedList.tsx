import type { Key, ReactNode } from 'react';
import type { Variants } from 'framer-motion';
import { MotionBox, type MotionBoxProps } from './motion';

const containerVariants: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08 } },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
};

export interface AnimatedListProps<T> extends Omit<MotionBoxProps, 'children'> {
  items: readonly T[];
  renderItem: (item: T, index: number) => ReactNode;
  getKey: (item: T, index: number) => Key;
  /** Vertical gap between items (Chakra spacing token). Ignored if `display="grid"` with your own gap. */
  gap?: MotionBoxProps['gap'];
}

/** Staggered fade-in list. Pass `display="grid"` + `gridTemplateColumns` for a card grid. */
export function AnimatedList<T>({ items, renderItem, getKey, gap = 4, ...rest }: AnimatedListProps<T>) {
  return (
    <MotionBox
      initial="hidden"
      animate="visible"
      variants={containerVariants}
      display="flex"
      flexDirection="column"
      gap={gap}
      {...rest}
    >
      {items.map((item, index) => (
        <MotionBox key={getKey(item, index)} variants={itemVariants}>
          {renderItem(item, index)}
        </MotionBox>
      ))}
    </MotionBox>
  );
}
