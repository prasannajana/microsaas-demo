import { forwardRef } from 'react';
import { FormControl, FormErrorMessage, FormHelperText, FormLabel } from '@chakra-ui/react';
import { MotionInput, type MotionInputProps } from './motion';

export interface AnimatedInputProps extends MotionInputProps {
  label?: string;
  error?: string;
  helperText?: string;
}

export const AnimatedInput = forwardRef<HTMLInputElement, AnimatedInputProps>(function AnimatedInput(
  { label, error, helperText, isRequired, id, name, ...rest },
  ref,
) {
  const inputId = id ?? name;
  return (
    <FormControl isInvalid={Boolean(error)} isRequired={isRequired}>
      {label && <FormLabel htmlFor={inputId}>{label}</FormLabel>}
      <MotionInput
        ref={ref}
        id={inputId}
        name={name}
        whileFocus={{ scale: 1.01 }}
        transition={{ duration: 0.15 }}
        size="lg"
        borderRadius="xl"
        borderWidth="2px"
        bg="whiteAlpha.800"
        focusBorderColor="brand.500"
        errorBorderColor="red.400"
        {...rest}
      />
      {error ? (
        <FormErrorMessage>{error}</FormErrorMessage>
      ) : (
        helperText && <FormHelperText>{helperText}</FormHelperText>
      )}
    </FormControl>
  );
});
