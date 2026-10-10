import { MotionButton, type MotionButtonProps } from '../ui/motion';

/** Secondary (non-gradient) button with the mandatory hover/tap animation. */
export function ActionButton({ isDisabled, isLoading, ...rest }: MotionButtonProps) {
  const inactive = Boolean(isDisabled) || Boolean(isLoading);
  return (
    <MotionButton
      whileHover={inactive ? undefined : { scale: 1.03, y: -1 }}
      whileTap={inactive ? undefined : { scale: 0.97 }}
      isDisabled={isDisabled}
      isLoading={isLoading}
      {...rest}
    />
  );
}
