import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { RingListItem } from '../api/client';
import { useWebSocket } from '../hooks/useWebSocket';
import { RiskBadge } from '../components/RiskBadge';
import {
  TrendingUp,
  Clock,
  Layers,
  Activity,
} from 'lucide-react';

export function RiskTimeline() {
  const { events, latestUpdate } = useWebSocket();
  const [rings, setRings] = useState<RingListItem[]>([]);
  const [selectedClusterId, setSelectedClusterId] = useState<number | null>(null);
  const [timelineData, setTimelineData] = useState<Array<{ timestamp: string; risk_score: number }>>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.listRings()
      .then((data) => {
        setRings(data);
        if (data.length > 0) {
          // Extract cluster id from top ring or default to 1
          setSelectedClusterId(1);
        }
      })
      .catch((err) => console.error(err));
  }, []);

  useEffect(() => {
    if (selectedClusterId === null) return;
    setLoading(true);
    api.getRiskTimeline(selectedClusterId)
      .then((res) => {
        setTimelineData(res.timeline || []);
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [selectedClusterId, latestUpdate]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
              <TrendingUp className="h-6 w-6 text-cyan-400" />
              Live Risk Evolution Timeline
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
              State-Space Trajectory
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Observe real-time risk scores escalating as structural and behavioral evidence accumulates. No pre-staged curves.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Ring / Cluster Selector */}
        <div className="card p-4 space-y-3">
          <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5 border-b border-slate-800 pb-2.5">
            <Layers className="h-4 w-4 text-cyan-400" />
            Detected Clusters ({rings.length})
          </h2>

          <div className="space-y-1.5 max-h-[500px] overflow-y-auto pr-1">
            {rings.map((r, i) => {
              const clusterId = i + 1;
              const isSelected = selectedClusterId === clusterId;
              return (
                <div
                  key={r.ring_id}
                  onClick={() => setSelectedClusterId(clusterId)}
                  className={`p-3 rounded border cursor-pointer transition flex items-center justify-between ${
                    isSelected
                      ? 'bg-cyan-950/60 border-cyan-500/80'
                      : 'bg-slate-900/60 border-slate-800 hover:bg-slate-800/60'
                  }`}
                >
                  <div>
                    <div className="font-bold text-xs text-slate-200 flex items-center gap-1.5">
                      {r.ring_id}
                      <span className="text-[10px] text-slate-400 font-normal">
                        ({r.account_count} accounts)
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      {r.top_evidence_type ? r.top_evidence_type.replace(/_/g, ' ') : 'Multi-signal'}
                    </div>
                  </div>
                  <RiskBadge score={r.risk_score} band={r.risk_band} />
                </div>
              );
            })}
          </div>
        </div>

        {/* Timeline Visualization & Trajectory */}
        <div className="lg:col-span-2 space-y-6">
          {/* Main Visual Curve Card */}
          <div className="card p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                  <Activity className="h-4 w-4 text-cyan-400" />
                  Cluster #{selectedClusterId} Risk Score Trajectory
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Points represent actual scoring evaluation moments as payment events arrived.
                </p>
              </div>
              <span className="text-xs text-slate-400 font-mono">
                {timelineData.length} observation points
              </span>
            </div>

            {loading ? (
              <div className="h-48 flex items-center justify-center text-slate-500 text-xs">
                Loading cluster trajectory...
              </div>
            ) : timelineData.length === 0 ? (
              <div className="h-48 flex flex-col items-center justify-center text-slate-500 text-xs space-y-2">
                <Clock className="h-6 w-6 opacity-30" />
                <p>No historical event updates recorded for Cluster #{selectedClusterId} yet.</p>
                <p className="text-[11px] text-slate-600">
                  Run a scenario or submit manual events to observe live timeline changes.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {/* SVG Risk Curve */}
                <div className="h-48 bg-slate-900/90 rounded border border-slate-800 p-3 relative flex items-end">
                  <svg className="w-full h-full overflow-visible" preserveAspectRatio="none">
                    <defs>
                      <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#6b4f3a" stopOpacity="0.32" />
                        <stop offset="100%" stopColor="#6b4f3a" stopOpacity="0.0" />
                      </linearGradient>
                    </defs>

                    {/* Horizontal threshold reference lines */}
                    <line x1="0" y1="15%" x2="100%" y2="15%" stroke="#6b4f3a" strokeDasharray="3 3" opacity="0.42" />
                    <line x1="0" y1="35%" x2="100%" y2="35%" stroke="#7d6048" strokeDasharray="3 3" opacity="0.42" />
                    <line x1="0" y1="60%" x2="100%" y2="60%" stroke="#987b5e" strokeDasharray="3 3" opacity="0.42" />

                    {/* Timeline polyline */}
                    {timelineData.length > 1 && (
                      <polyline
                        fill="none"
                        stroke="#6b4f3a"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        points={timelineData
                          .map((d, idx) => {
                            const x = (idx / (timelineData.length - 1)) * 100;
                            const y = 100 - (d.risk_score / 100) * 100;
                            return `${x}%,${y}%`;
                          })
                          .join(' ')}
                      />
                    )}

                    {/* Observation Points */}
                    {timelineData.map((d, idx) => {
                      const x = (idx / Math.max(timelineData.length - 1, 1)) * 100;
                      const y = 100 - (d.risk_score / 100) * 100;
                      return (
                        <circle
                          key={idx}
                          cx={`${x}%`}
                          cy={`${y}%`}
                          r="4"
                          className={`${
                            d.risk_score >= 85
                              ? 'fill-rose-400 stroke-rose-950'
                              : d.risk_score >= 65
                              ? 'fill-amber-400 stroke-amber-950'
                              : 'fill-cyan-400 stroke-cyan-950'
                          } stroke-2`}
                        />
                      );
                    })}
                  </svg>
                </div>

                {/* Score Log Table */}
                <div className="overflow-x-auto max-h-48 overflow-y-auto">
                  <table className="w-full text-left text-xs font-mono border-collapse">
                    <thead className="bg-slate-900 text-slate-400 sticky top-0 border-b border-slate-800">
                      <tr>
                        <th className="py-1.5 px-3">Step</th>
                        <th className="py-1.5 px-3">Timestamp</th>
                        <th className="py-1.5 px-3">Computed Risk</th>
                        <th className="py-1.5 px-3 text-right">Band</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 text-slate-300">
                      {timelineData.map((d, i) => (
                        <tr key={i} className="hover:bg-slate-800/40">
                          <td className="py-1.5 px-3 text-slate-500">#{i + 1}</td>
                          <td className="py-1.5 px-3">{new Date(d.timestamp).toLocaleTimeString()}</td>
                          <td className="py-1.5 px-3 font-bold text-cyan-400">{d.risk_score.toFixed(1)}</td>
                          <td className="py-1.5 px-3 text-right">
                            {d.risk_score >= 85 ? (
                              <span className="text-rose-400 font-bold">Critical</span>
                            ) : d.risk_score >= 65 ? (
                              <span className="text-amber-400 font-bold">High</span>
                            ) : d.risk_score >= 40 ? (
                              <span className="text-yellow-400">Medium</span>
                            ) : (
                              <span className="text-emerald-400">Low</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* Real-Time Telemetry Stream Inflection Feed */}
          <div className="card p-4 space-y-3">
            <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <Clock className="h-4 w-4 text-cyan-400" />
              Latest Live Stream Inflections (Global)
            </h4>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {events.slice(0, 5).map((ev) => (
                <div
                  key={ev.event_id}
                  className="p-2.5 rounded bg-slate-900/80 border border-slate-800 flex items-center justify-between text-xs font-mono"
                >
                  <div>
                    <span className="text-slate-400">{new Date(ev.timestamp).toLocaleTimeString()}</span>
                    <span className="text-slate-200 font-bold mx-2">{ev.buyer_id}</span>
                    <span className="text-slate-500">→</span>
                    <span className="text-slate-300 ml-2">{ev.merchant_id}</span>
                    <span className="text-slate-400 ml-2">₹{ev.amount}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`font-bold ${
                        ev.risk_score >= 65 ? 'text-rose-400' : 'text-emerald-400'
                      }`}
                    >
                      {ev.risk_score.toFixed(1)}
                    </span>
                    {ev.alert_triggered && (
                      <span className="text-[10px] text-rose-400 font-bold px-1.5 py-0.5 bg-rose-950/80 rounded border border-rose-800">
                        ALERT
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
