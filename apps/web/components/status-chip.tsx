import React from 'react';

type StatusChipProps = {
  tone?: 'neutral' | 'good' | 'warn' | 'bad' | 'info';
  animated?: boolean;
  children: React.ReactNode;
};

export function StatusChip({ tone = 'neutral', animated = false, children }: StatusChipProps) {
  return (
    <span className={`status-chip status-chip--${tone} ${animated ? 'status-chip--animated' : ''}`}>
      {children}
    </span>
  );
}
