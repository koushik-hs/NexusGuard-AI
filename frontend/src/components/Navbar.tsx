import React from 'react';
import { Network, BarChart2, Search, Activity } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';

const NAV_ITEMS = [
  { path: '/',         label: 'Risk Overview',      icon: Activity },
  { path: '/metrics',  label: 'Detection Metrics',  icon: BarChart2 },
];

export function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <div className="navbar-brand-icon">
          <Network size={16} color="#fff" />
        </div>
        <div className="navbar-brand-text">
          <span className="navbar-brand-title">RING DETECTOR</span>
          <span className="navbar-brand-subtitle">Razorpay Risk — AI Buildathon</span>
        </div>
      </div>

      <div className="navbar-nav">
        {NAV_ITEMS.map(({ path, label, icon: Icon }) => (
          <button
            key={path}
            className={`nav-item ${location.pathname === path ? 'active' : ''}`}
            onClick={() => navigate(path)}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      <div className="navbar-status">
        <div className="status-dot" />
        <span>Graph Engine Active</span>
      </div>
    </nav>
  );
}
