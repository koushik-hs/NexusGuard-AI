interface NexusGuardBrandProps {
  compact?: boolean;
  className?: string;
}

/** The single product mark used across NEXUSGUARD AI surfaces. */
export function NexusGuardBrand({ compact = false, className = '' }: NexusGuardBrandProps) {
  return (
    <div className={`nexusguard-brand ${compact ? 'is-compact' : ''} ${className}`}>
      <svg className="nexusguard-mark" viewBox="0 0 48 48" role="img" aria-label="NEXUSGUARD AI">
        <path d="M24 7 41 24 24 41 7 24Z" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="24" cy="7" r="5.5" fill="currentColor" />
        <circle cx="41" cy="24" r="5.5" fill="currentColor" />
        <circle cx="24" cy="41" r="5.5" fill="currentColor" />
        <circle cx="7" cy="24" r="5.5" fill="currentColor" />
      </svg>
      {!compact && <div className="nexusguard-wordmark"><strong>NEXUSGUARD <em>AI</em></strong><span>Payment Risk Intelligence Platform</span></div>}
    </div>
  );
}
