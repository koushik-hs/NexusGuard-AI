import React from 'react';

interface Props {
  label: string;
  value: string | number;
  sub?: string;
  accent?: boolean;
  large?: boolean;
}

export function MetricCard({ label, value, sub, accent, large }: Props) {
  return (
    <div className="metric-card" style={accent ? {
      borderColor: 'rgba(37,99,235,0.3)',
      background: 'rgba(37,99,235,0.06)',
    } : undefined}>
      <div className="metric-label">{label}</div>
      <div
        className="metric-value"
        style={{
          fontSize: large ? 32 : 24,
          color: accent ? 'var(--accent)' : 'var(--text-primary)',
        }}
      >
        {value}
      </div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  );
}
