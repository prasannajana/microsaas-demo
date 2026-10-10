import { Box, Button, Input } from '@chakra-ui/react';
import { motion } from 'framer-motion';

/** Chakra primitives enhanced with framer-motion props (whileHover, whileTap, variants, ...). */
export const MotionBox = motion.create(Box);
export const MotionButton = motion.create(Button);
export const MotionInput = motion.create(Input);

export type MotionBoxProps = React.ComponentProps<typeof MotionBox>;
export type MotionButtonProps = React.ComponentProps<typeof MotionButton>;
export type MotionInputProps = React.ComponentProps<typeof MotionInput>;
