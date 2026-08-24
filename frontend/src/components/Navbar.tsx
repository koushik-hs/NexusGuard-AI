import { Activity, Radio, Send, Share2, BarChart2, HeartPulse } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useLiveData } from '../context/LiveDataContext';
import { NexusGuardBrand } from './NexusGuardBrand';

const NAV_ITEMS = [
  { path: '/',           label: 'Overview',          icon: Activity },
  { path: '/live',       label: 'Live Monitor',      icon: Radio },
  { path: '/graph',      label: 'Graph Explorer',    icon: Share2 },
  { path: '/metrics',    label: 'Detection Models',  icon: BarChart2 },
  { path: '/simulator',  label: 'Event Simulator',   icon: Send },
];

export function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isConnected, activeAlerts, status, latestUpdate } = useLiveData();

  return (
    <nav className="navbar" aria-label="Primary navigation">
      <div className="navbar-brand">
        <NexusGuardBrand />
      </div>

      <div className="navbar-nav">
        {NAV_ITEMS.map(({ path, label, icon: Icon }) => {
          const isActive =
            path === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(path);
          return (
            <button
              key={path}
              className={`nav-item ${isActive ? 'active' : ''}`}
              onClick={() => navigate(path)}
            >
              <Icon size={14} />
              <span>{label}</span>
              {path === '/live' && activeAlerts.length > 0 && (
                <span className="nav-alert-count">
                  {activeAlerts.length}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="navbar-status" aria-live="polite">
        <div
          className={`status-dot ${
            isConnected ? 'bg-emerald-400' : 'bg-rose-400'
          }`}
          style={{ width: 7, height: 7, borderRadius: '50%' }}
        />
        <span>
          {isConnected ? 'STREAM CONNECTED' : 'STREAM DISCONNECTED'}
        </span>
      </div>
      <div className="sidebar-health">
        <div className="sidebar-health-title"><HeartPulse size={14} /> SYSTEM HEALTH</div>
        <div><span className={`health-dot ${status?.initialized ? 'healthy' : ''}`} /> Graph engine <b>{status?.initialized ? 'ready' : 'unavailable'}</b></div>
        <div><span className={`health-dot ${status?.xgboost_loaded ? 'healthy' : ''}`} /> XGBoost <b>{status?.xgboost_loaded ? 'loaded' : 'unavailable'}</b></div>
        <div><span className={`health-dot ${status?.if_loaded ? 'healthy' : ''}`} /> Isolation Forest <b>{status?.if_loaded ? 'loaded' : 'unavailable'}</b></div>
        <div className="last-event">{latestUpdate ? <>LAST EVENT <strong>{new Date(latestUpdate.timestamp).toLocaleTimeString()}</strong></> : <>LAST EVENT <strong>none received</strong></>}</div>
      </div>
    </nav>
  );
}
