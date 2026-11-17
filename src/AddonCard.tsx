import { useState, type ReactNode } from 'react';
import { DialogButton } from '@decky/ui';

type AddonCardProps = {
  name: string;
  icon?: string;
  version?: string | null;
  status?: string;
  warning?: boolean;
  children: ReactNode;
  action?: ReactNode;
};

const ICON = 32;

// The project's logo from CurseForge, or its initial when there is none or it fails to load.
function AddonIcon({ name, icon }: { name: string; icon?: string }) {
  const [failed, setFailed] = useState(false);
  const box = { width: ICON, height: ICON, flexShrink: 0, borderRadius: 4 } as const;
  if (icon && !failed) {
    return <img src={icon} alt="" width={ICON} height={ICON} loading="lazy" referrerPolicy="no-referrer"
      onError={() => setFailed(true)} style={{ ...box, objectFit: 'cover', background: 'rgba(255, 255, 255, 0.06)' }} />;
  }
  return <span aria-hidden="true" style={{ ...box, display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: 'rgba(255, 255, 255, 0.08)', fontSize: 14, fontWeight: 600, color: '#8b929a' }}>
    {name.trim().charAt(0).toUpperCase() || '?'}</span>;
}

export function AddonCard({ name, icon, version, status, warning, children, action }: AddonCardProps) {
  const [expanded, setExpanded] = useState(false);
  return <div style={{
    margin: '8px 0', border: '1px solid #59616e', borderRadius: 6,
    background: 'rgba(0, 0, 0, 0.16)',
  }}>
    <DialogButton onClick={() => setExpanded(value => !value)} {...{'aria-expanded': expanded}}
      style={{ display: 'block', width: '100%', minWidth: 0, padding: '10px 12px',
        boxSizing: 'border-box', textAlign: 'left', borderRadius: 5 }}>
      <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <AddonIcon key={icon} name={name} icon={icon} />
        <span style={{ flex: 1, minWidth: 0 }}>
          <span style={{ display: 'block', fontSize: 14, fontWeight: 600,
            lineHeight: 1.3, whiteSpace: 'normal', overflowWrap: 'anywhere' }}>{name}</span>
          {version !== undefined && <span style={{ display: 'block', marginTop: 3,
            fontSize: 12, lineHeight: 1.3, fontWeight: 400, whiteSpace: 'normal',
            overflowWrap: 'anywhere' }}>{version || 'Version unknown'}</span>}
          {status && <span style={{ display: 'block', marginTop: 3, fontSize: 12,
            lineHeight: 1.3, whiteSpace: 'normal', color: warning ? '#ffd49a' : '#a9dcff' }}>{status}</span>}
        </span>
        <span aria-label={expanded ? 'Hide details' : 'Show details'}
          style={{ fontSize: 12, flexShrink: 0 }}>{expanded ? '▾' : '▸'}</span>
      </span>
    </DialogButton>
    {expanded && <div style={{ padding: '10px 12px', borderTop: '1px solid #59616e',
      fontSize: 13, lineHeight: 1.4, overflowWrap: 'anywhere' }}>{children}</div>}
    {action && <div style={{ padding: '0 12px 10px' }}>{action}</div>}
  </div>;
}
