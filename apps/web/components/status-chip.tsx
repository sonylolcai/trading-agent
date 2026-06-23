type StatusChipProps = {
  tone?: 'neutral' | 'good' | 'warn' | 'bad' | 'info';
  children: React.ReactNode;
};

export function StatusChip({ tone = 'neutral', children }: StatusChipProps) {
  return <span className={`status-chip status-chip--${tone}`}>{children}</span>;
}
