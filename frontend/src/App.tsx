import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import './index.css';
import { Navbar } from './components/Navbar';
import { RiskOverview } from './screens/RiskOverview';
import { LiveEventStream } from './screens/LiveEventStream';
import { ManualEventSimulator } from './screens/ManualEventSimulator';
import { RiskTimeline } from './screens/RiskTimeline';
import { RingInvestigation } from './screens/RingInvestigation';
import { GraphExplorer } from './screens/GraphExplorer';
import { DetectionMetrics } from './screens/DetectionMetrics';
import { LiveDataProvider } from './context/LiveDataContext';

function App() {
  return (
    <BrowserRouter>
      <ApplicationShell />
    </BrowserRouter>
  );
}

const PAGE_TITLES: Record<string, string> = {
  '/': 'Overview',
  '/live': 'Live Monitor',
  '/graph': 'Graph Explorer',
  '/metrics': 'Detection Models',
  '/simulator': 'Event Simulator',
  '/timeline': 'Risk Timeline',
};

function ApplicationShell() {
  const location = useLocation();

  useEffect(() => {
    const page = location.pathname.startsWith('/ring/')
      ? 'Investigation'
      : PAGE_TITLES[location.pathname] || 'Payment Risk Intelligence';
    document.title = `NEXUSGUARD AI | ${page}`;
  }, [location.pathname]);

  return (
      <LiveDataProvider>
        <div className="app-layout">
          <Navbar />
          <main className="app-content">
            <div className="route-transition" key={location.pathname}>
              <Routes location={location}>
                <Route path="/" element={<RiskOverview />} />
                <Route path="/live" element={<LiveEventStream />} />
                <Route path="/simulator" element={<ManualEventSimulator />} />
                <Route path="/timeline" element={<RiskTimeline />} />
                <Route path="/ring/:ringId" element={<RingInvestigation />} />
                <Route path="/graph/:ringId?" element={<GraphExplorer />} />
                <Route path="/metrics" element={<DetectionMetrics />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </div>
          </main>
        </div>
      </LiveDataProvider>
  );
}

export default App;
