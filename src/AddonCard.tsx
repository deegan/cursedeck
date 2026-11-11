import { useState, type ReactNode } from 'react';
import { DialogButton } from '@decky/ui';

type AddonCardProps = {
  name: string;
  version?: string | null;
  status?: string;
  warning?: boolean;
  children: ReactNode;
  action?: ReactNode;
};

export function AddonCard({ name, version, status, warning, children, action }: AddonCardProps) {
  const [expanded, setExpanded] = useState(false);
  return <div style={{
    margin: '8px 0', border: '1px solid #59616e', borderRadius: 6,
    background: 'rgba(0, 0, 0, 0.16)',
  }}>
    <DialogButton onClick={() => setExpanded(value => !value)} {...{'aria-expanded': expanded}}
      style={{ display: 'block', width: '100%', minWidth: 0, padding: '10px 12px',
        boxSizing: 'border-box', textAlign: 'left', borderRadius: 5 }}>
      <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
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
