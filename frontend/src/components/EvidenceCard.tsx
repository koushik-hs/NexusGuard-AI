import type React from 'react';
import {
  Monitor, Wifi, RefreshCw, GitBranch, Users,
  Clock, TrendingUp, AlertCircle,
} from 'lucide-react';
import type { EvidenceItem } from '../api/client';

const EVIDENCE_ICONS: Record<string, React.ElementType> = {
  shared_device:           Monitor,
  shared_ip:               Wifi,
  refund_ratio:            RefreshCw,
  circular_flow:           GitBranch,
  transaction_concentration: Users,
  temporal_sync:           Clock,
  high_velocity:           TrendingUp,
};

const EVIDENCE_COLORS: Record<string, string> = {
  shared_device:           '#6b4f3a',
  shared_ip:               '#7d6048',
  refund_ratio:            '#987b5e',
  circular_flow:           '#8a735f',
  transaction_concentration: '#a78c6b',
  temporal_sync:           '#c9b79c',
  high_velocity:           '#6b4f3a',
};

interface Props {
  item: EvidenceItem;
}

export function EvidenceCard({ item }: Props) {
  const Icon = EVIDENCE_ICONS[item.type] || AlertCircle;
  const color = EVIDENCE_COLORS[item.type] || '#6b4f3a';
  const label = item.type.replace(/_/g, ' ');

  return (
    <div className="evidence-item" style={{ borderLeftColor: color }}>
      <div className="evidence-icon" style={{
        background: `${color}18`,
        color,
      }}>
        <Icon size={14} />
      </div>
      <div className="evidence-content">
        <div className="evidence-type">{label}</div>
        <div className="evidence-detail">{item.detail}</div>
      </div>
    </div>
  );
}
