import { Heading, type HeadingProps } from '@chakra-ui/react';
import type { Variants } from 'framer-motion';
import { MotionBox } from './motion';

const containerVariants: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06 } },
};

const wordVariants: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0 },
};

export interface TextRevealProps extends Omit<HeadingProps, 'children'> {
  text: string;
  /** Apply the brand gradient to the text (default true). */
  gradient?: boolean;
}

/** Headline that reveals word by word. */
export function TextReveal({ text, gradient = true, ...rest }: TextRevealProps) {
  const words = text.split(' ');
  return (
    <Heading {...rest}>
      <MotionBox as="span" initial="hidden" animate="visible" variants={containerVariants}>
        {words.map((word, i) => (
          <MotionBox
            as="span"
            key={`${word}-${i}`}
            display="inline-block"
            whiteSpace="pre"
            bgGradient={gradient ? 'linear(to-r, brand.600, accent.500)' : undefined}
            bgClip={gradient ? 'text' : undefined}
            variants={wordVariants}
          >
            {i < words.length - 1 ? `${word} ` : word}
          </MotionBox>
        ))}
      </MotionBox>
    </Heading>
  );
}
