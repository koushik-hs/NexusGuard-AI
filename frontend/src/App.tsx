import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import './index.css';
import { Navbar } from './components/Navbar';
import { RiskOverview } from './screens/RiskOverview';
import { RingInvestigation } from './screens/RingInvestigation';
import { GraphExplorer } from './screens/GraphExplorer';
import { DetectionMetrics } from './screens/DetectionMetrics';

function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Navbar />
        <main className="app-content">
          <Routes>
            <Route path="/"                element={<RiskOverview />} />
            <Route path="/ring/:ringId"    element={<RingInvestigation />} />
            <Route path="/graph/:ringId?"  element={<GraphExplorer />} />
            <Route path="/metrics"         element={<DetectionMetrics />} />
            <Route path="*"               element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
