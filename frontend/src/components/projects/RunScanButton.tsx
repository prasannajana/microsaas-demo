import { GradientButton, type GradientButtonProps } from '../ui/GradientButton';

export interface RunScanButtonProps extends Omit<GradientButtonProps, 'children' | 'onClick'> {
  onRun: () => void;
  /** True while a scan is being requested or is queued/running. */
  isActive: boolean;
  label?: string;
}

export function RunScanButton({ onRun, isActive, label = 'Run scan', ...rest }: RunScanButtonProps) {
  return (
    <GradientButton
      onClick={onRun}
      isLoading={isActive}
      loadingText="Scanning…"
      isDisabled={isActive}
      aria-label={isActive ? 'Scan in progress' : label}
      {...rest}
    >
      {label}
    </GradientButton>
  );
}
