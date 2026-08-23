import React from 'react';
import {
  Monitor, Wifi, RefreshCw, GitBranch, Users,
  Clock, TrendingUp, AlertCircle, Zap,
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
  shared_device:           '#dc2626',
  shared_ip:               '#ea580c',
  refund_ratio:            '#ca8a04',
  circular_flow:           '#9333ea',
  transaction_concentration: '#0f766e',
  temporal_sync:           '#0369a1',
  high_velocity:           '#be185d',
};

interface Props {
  item: EvidenceItem;
}

export function EvidenceCard({ item }: Props) {
  const Icon = EVIDENCE_ICONS[item.type] || AlertCircle;
  const color = EVIDENCE_COLORS[item.type] || '#2563eb';
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
