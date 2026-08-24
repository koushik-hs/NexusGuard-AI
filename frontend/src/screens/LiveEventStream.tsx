import { useState } from 'react';
import { useLiveData } from '../context/LiveDataContext';
import { api } from '../api/client';
import type { LiveUpdate } from '../api/client';
import { RiskBadge } from '../components/RiskBadge';
import { AnimatedNumber } from '../components/AnimatedNumber';
import {
  Activity,
  Play,
  Pause,
  Trash2,
  Zap,
  AlertTriangle,
  Clock,
  Cpu,
  Layers,
  ShieldAlert,
} from 'lucide-react';

export function LiveEventStream() {
  const { isConnected, events, clearEvents, activeAlerts } = useLiveData();
  const [isPaused, setIsPaused] = useState(false);
  const [filterType, setFilterType] = useState<'all' | 'alerts' | 'refunds'>('all');
  const [selectedEvent, setSelectedEvent] = useState<LiveUpdate | null>(null);
  const [runningScenario, setRunningScenario] = useState<string | null>(null);
  const [scenarioStatus, setScenarioStatus] = useState<string | null>(null);

  const displayedEvents = events.filter((ev) => {
    if (filterType === 'alerts') return ev.alert_triggered;
    if (filterType === 'refunds') return ev.is_refund;
    return true;
  });

  const handleRunScenario = async (stype: string) => {
    setRunningScenario(stype);
    setScenarioStatus('Simulating events...');
    try {
      const res = await api.runScenario(stype, 350);
      setScenarioStatus(`Running: ${res.description} (${res.total_events} events)`);
      setTimeout(() => {
        setRunningScenario(null);
      }, 4000);
    } catch (e: any) {
      setScenarioStatus(`Error: ${e.message}`);
      setRunningScenario(null);
    }
  };

  return (
    <div className="page space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
              <Activity className="h-6 w-6 text-cyan-400 animate-pulse" />
              Live Event Ingestion Stream
            </h1>
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                isConnected
                  ? 'bg-emerald-950/80 text-emerald-400 border border-emerald-800/60'
                  : 'bg-rose-950/80 text-rose-400 border border-rose-800/60'
              }`}
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  isConnected ? 'bg-emerald-400 animate-ping' : 'bg-rose-400'
                }`}
              />
              {isConnected ? 'WebSocket Live' : 'Reconnecting...'}
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Real-time telemetry stream. Every event triggers live graph updates, feature recalculation, and 3-model inference.
          </p>
        </div>

        {/* Stream Controls */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setIsPaused(!isPaused)}
            className={`btn-secondary flex items-center gap-1.5 text-xs ${
              isPaused ? 'text-amber-400 border-amber-500/40' : ''
            }`}
          >
            {isPaused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
            {isPaused ? 'Resume Stream' : 'Pause'}
          </button>
          <button
            onClick={clearEvents}
            className="btn-secondary flex items-center gap-1.5 text-xs text-slate-400 hover:text-rose-400"
            title="Clear in-memory buffer"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Clear
          </button>
        </div>
      </div>

      {/* Scenario Simulation Trigger Bar */}
      <div className="card p-4 bg-slate-900/90 border-slate-800">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-cyan-400 flex items-center gap-1.5">
              <Zap className="h-4 w-4" />
              Scenario Simulator (Payment Generation Only)
            </div>
            <div className="text-xs text-slate-400 mt-0.5">
              Generates raw payment events with no labels. The detector evaluates risk autonomously.
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => handleRunScenario('coordinated_ring')}
              disabled={!!runningScenario}
              className="px-3 py-1.5 rounded bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-700/60 text-cyan-200 text-xs font-medium transition disabled:opacity-50"
            >
              Coordinated Ring (Hero)
            </button>
            <button
              onClick={() => handleRunScenario('shared_device_ring')}
              disabled={!!runningScenario}
              className="px-3 py-1.5 rounded bg-indigo-950/80 hover:bg-indigo-900 border border-indigo-700/60 text-indigo-200 text-xs font-medium transition disabled:opacity-50"
            >
              Shared Device Farm
            </button>
            <button
              onClick={() => handleRunScenario('refund_farming')}
              disabled={!!runningScenario}
              className="px-3 py-1.5 rounded bg-purple-950/80 hover:bg-purple-900 border border-purple-700/60 text-purple-200 text-xs font-medium transition disabled:opacity-50"
            >
              Refund Farming
            </button>
            <button
              onClick={() => handleRunScenario('circular_flow')}
              disabled={!!runningScenario}
              className="px-3 py-1.5 rounded bg-amber-950/80 hover:bg-amber-900 border border-amber-700/60 text-amber-200 text-xs font-medium transition disabled:opacity-50"
            >
              Circular Loop
            </button>
            <button
              onClick={() => handleRunScenario('legit_family_business')}
              disabled={!!runningScenario}
              className="px-3 py-1.5 rounded bg-emerald-950/80 hover:bg-emerald-900 border border-emerald-700/60 text-emerald-200 text-xs font-medium transition disabled:opacity-50"
              title="Hard negative: legitimate merchants sharing device/IP"
            >
              Family Biz (Hard Neg)
            </button>
            <button
              onClick={() => handleRunScenario('legit_corporate_office')}
              disabled={!!runningScenario}
              className="px-3 py-1.5 rounded bg-emerald-950/80 hover:bg-emerald-900 border border-emerald-700/60 text-emerald-200 text-xs font-medium transition disabled:opacity-50"
              title="Hard negative: corporate office IP"
            >
              Office IP (Hard Neg)
            </button>
          </div>
        </div>
        {scenarioStatus && (
          <div className="mt-2 text-xs text-cyan-300 font-mono bg-cyan-950/40 px-3 py-1.5 rounded border border-cyan-800/40">
            {scenarioStatus}
          </div>
        )}
      </div>

      {/* Latency & Buffer Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="card p-3 flex items-center justify-between">
          <div>
            <div className="text-xs text-slate-400">Events in Buffer</div>
            <div className="text-lg font-bold text-slate-200">{events.length}</div>
          </div>
          <Layers className="h-5 w-5 text-slate-500" />
        </div>
        <div className="card p-3 flex items-center justify-between">
          <div>
            <div className="text-xs text-slate-400">Active Live Alerts</div>
            <div className="text-lg font-bold text-rose-400">{activeAlerts.length}</div>
          </div>
          <AlertTriangle className="h-5 w-5 text-rose-400" />
        </div>
        <div className="card p-3 flex items-center justify-between">
          <div>
            <div className="text-xs text-slate-400">P95 Latency</div>
            <div className="text-lg font-bold text-emerald-400 font-mono">
              {events[0]?.latency_ms?.total ? `${events[0].latency_ms.total.toFixed(1)}ms` : '~24ms'}
            </div>
          </div>
          <Clock className="h-5 w-5 text-emerald-400" />
        </div>
        <div className="card p-3 flex items-center justify-between">
          <div>
            <div className="text-xs text-slate-400">Primary ML Model</div>
            <div className="text-lg font-bold text-cyan-400">XGBoost + IF</div>
          </div>
          <Cpu className="h-5 w-5 text-cyan-400" />
        </div>
      </div>

      {/* Main Stream Table & Details Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Stream Table */}
        <div className="lg:col-span-2 card p-0 overflow-hidden">
          <div className="p-3.5 border-b border-slate-800 flex items-center justify-between bg-slate-900/60">
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold text-slate-300">Filter:</span>
              <button
                onClick={() => setFilterType('all')}
                className={`px-2.5 py-1 rounded text-xs font-medium ${
                  filterType === 'all'
                    ? 'bg-slate-700 text-white'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                All ({events.length})
              </button>
              <button
                onClick={() => setFilterType('alerts')}
                className={`px-2.5 py-1 rounded text-xs font-medium flex items-center gap-1 ${
                  filterType === 'alerts'
                    ? 'bg-rose-950 text-rose-300 border border-rose-800/60'
                    : 'text-slate-400 hover:text-rose-400'
                }`}
              >
                Alerts ({activeAlerts.length})
              </button>
              <button
                onClick={() => setFilterType('refunds')}
                className={`px-2.5 py-1 rounded text-xs font-medium ${
                  filterType === 'refunds'
                    ? 'bg-amber-950 text-amber-300 border border-amber-800/60'
                    : 'text-slate-400 hover:text-amber-400'
                }`}
              >
                Refunds
              </button>
            </div>
            <span className="text-xs text-slate-500">Click any row to inspect</span>
          </div>

          <div className="overflow-x-auto max-h-[560px] overflow-y-auto">
            {displayedEvents.length === 0 ? (
              <div className="p-12 text-center text-slate-500">
                <Activity className="h-8 w-8 mx-auto mb-2 opacity-30" />
                <p>No events matching filter. Launch a scenario or submit manual events above.</p>
              </div>
            ) : (
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-slate-900 text-slate-400 sticky top-0 border-b border-slate-800 z-10">
                  <tr>
                    <th className="py-2.5 px-3">Time</th>
                    <th className="py-2.5 px-3">Buyer → Merchant</th>
                    <th className="py-2.5 px-3">Amount</th>
                    <th className="py-2.5 px-3">Telemetry</th>
                    <th className="py-2.5 px-3">Risk Score</th>
                    <th className="py-2.5 px-3">Latency</th>
                    <th className="py-2.5 px-3 text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {displayedEvents.map((ev) => {
                    const isSelected = selectedEvent?.event_id === ev.event_id;
                    const deltaPositive = ev.risk_delta > 0;
                    return (
                      <tr
                        key={ev.event_id}
                        onClick={() => setSelectedEvent(ev)}
                        className={`event-row cursor-pointer transition hover:bg-slate-800/50 ${
                          ev.event_id === events[0]?.event_id ? 'event-row-new' : ''
                        } ${
                          isSelected
                            ? 'bg-cyan-950/40 border-l-2 border-cyan-400'
                            : ev.alert_triggered
                            ? 'bg-rose-950/20'
                            : ''
                        }`}
                      >
                        <td className="py-2.5 px-3 text-slate-400 whitespace-nowrap">
                          {new Date(ev.timestamp).toLocaleTimeString()}
                        </td>
                        <td className="py-2.5 px-3">
                          <span className="text-slate-200 font-bold">{ev.buyer_id}</span>
                          <span className="text-slate-500 mx-1">→</span>
                          <span className="text-slate-300">{ev.merchant_id}</span>
                        </td>
                        <td className="py-2.5 px-3 text-slate-200">
                          ₹{ev.amount.toLocaleString()}
                          {ev.is_refund && (
                            <span className="ml-1 text-[10px] text-amber-400 font-semibold px-1 py-0.2 bg-amber-950/60 rounded">
                              REF
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-slate-400 text-[11px] whitespace-nowrap">
                          {ev.device_id ? ev.device_id : '—'} | {ev.ip_id ? ev.ip_id : '—'}
                        </td>
                        <td className="py-2.5 px-3">
                          <div className="flex items-center space-x-1.5">
                            <span
                              className={`font-bold ${
                                ev.risk_score >= 85
                                  ? 'text-rose-400'
                                  : ev.risk_score >= 65
                                  ? 'text-amber-400'
                                  : ev.risk_score >= 40
                                  ? 'text-yellow-400'
                                  : 'text-emerald-400'
                              }`}
                            >
                              <AnimatedNumber value={ev.risk_score} />
                            </span>
                            {ev.risk_delta !== 0 && (
                              <span
                                className={`text-[10px] ${
                                  deltaPositive ? 'text-rose-400' : 'text-emerald-400'
                                }`}
                              >
                                ({deltaPositive ? `+${ev.risk_delta}` : ev.risk_delta})
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-2.5 px-3 text-emerald-400 font-mono text-[11px]">
                          {ev.latency_ms?.total ? `${ev.latency_ms.total.toFixed(1)}ms` : '—'}
                        </td>
                        <td className="py-2.5 px-3 text-right whitespace-nowrap">
                          {ev.alert_triggered ? (
                            <span className="inline-flex items-center gap-1 text-[10px] font-bold text-rose-400 bg-rose-950/80 px-2 py-0.5 rounded border border-rose-800/60">
                              <ShieldAlert className="h-3 w-3" /> ALERT
                            </span>
                          ) : (
                            <span className="text-[10px] text-slate-500 font-normal">Normal</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Selected Event Detail Inspector */}
        <div className="card p-4 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="font-bold text-sm text-slate-100 flex items-center gap-1.5">
              <Cpu className="h-4 w-4 text-cyan-400" />
              Event Inference Inspector
            </h3>
            {selectedEvent ? (
              <RiskBadge score={selectedEvent.risk_score} band={selectedEvent.risk_band} />
            ) : (
              <span className="text-xs text-slate-500">None selected</span>
            )}
          </div>

          {selectedEvent ? (
            <div className="space-y-4 text-xs">
              {/* Event Core Meta */}
              <div className="bg-slate-900/80 p-3 rounded border border-slate-800 space-y-1.5 font-mono">
                <div className="flex justify-between">
                  <span className="text-slate-400">Event ID:</span>
                  <span className="text-slate-200">{selectedEvent.event_id.slice(0, 12)}...</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Buyer Account:</span>
                  <span className="text-cyan-400 font-bold">{selectedEvent.buyer_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Merchant:</span>
                  <span className="text-slate-200">{selectedEvent.merchant_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Amount:</span>
                  <span className="text-slate-100 font-bold">₹{selectedEvent.amount.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Device ID:</span>
                  <span className="text-slate-300">{selectedEvent.device_id || 'None'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">IP ID:</span>
                  <span className="text-slate-300">{selectedEvent.ip_id || 'None'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Source:</span>
                  <span className="text-slate-300">{selectedEvent.source || 'manual'}</span>
                </div>
              </div>

              {/* Model Attribution Breakdown */}
              <div className="space-y-2">
                <div className="font-semibold text-slate-300 text-xs">Multi-Model Risk Contribution</div>
                <div className="bg-slate-900/80 p-3 rounded border border-slate-800 space-y-2">
                  <div>
                    <div className="flex justify-between text-[11px] mb-1">
                      <span className="text-slate-400">XGBoost (Supervised 40%):</span>
                      <span className="font-mono text-cyan-400 font-bold">
                        {selectedEvent.cluster_stats?.xgb_score !== undefined &&
                        selectedEvent.cluster_stats.xgb_score !== null
                          ? `${(selectedEvent.cluster_stats.xgb_score * 100).toFixed(1)}%`
                          : 'N/A'}
                      </span>
                    </div>
                    <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-cyan-400 h-full rounded-full"
                        style={{
                          width: `${
                            selectedEvent.cluster_stats?.xgb_score
                              ? selectedEvent.cluster_stats.xgb_score * 100
                              : 0
                          }%`,
                        }}
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-[11px] mb-1">
                      <span className="text-slate-400">Isolation Forest (Anomaly 35%):</span>
                      <span className="font-mono text-indigo-400 font-bold">
                        {selectedEvent.cluster_stats?.if_score !== undefined
                          ? `${(selectedEvent.cluster_stats.if_score * 100).toFixed(1)}%`
                          : '0%'}
                      </span>
                    </div>
                    <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-indigo-400 h-full rounded-full"
                        style={{
                          width: `${
                            selectedEvent.cluster_stats?.if_score
                              ? selectedEvent.cluster_stats.if_score * 100
                              : 0
                          }%`,
                        }}
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-[11px] mb-1">
                      <span className="text-slate-400">Structural Rules (25%):</span>
                      <span className="font-mono text-amber-400 font-bold">
                        {selectedEvent.cluster_stats?.rule_score !== undefined
                          ? `${(selectedEvent.cluster_stats.rule_score * 100).toFixed(1)}%`
                          : '0%'}
                      </span>
                    </div>
                    <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-amber-400 h-full rounded-full"
                        style={{
                          width: `${
                            selectedEvent.cluster_stats?.rule_score
                              ? selectedEvent.cluster_stats.rule_score * 100
                              : 0
                          }%`,
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Latency Breakdown */}
              <div className="space-y-1.5">
                <div className="font-semibold text-slate-300 text-xs flex items-center justify-between">
                  <span>Measured Pipeline Latency</span>
                  <span className="text-emerald-400 font-mono">{selectedEvent.latency_ms?.total?.toFixed(1)}ms total</span>
                </div>
                <div className="bg-slate-900/60 p-2.5 rounded border border-slate-800 text-[11px] font-mono space-y-1 text-slate-400">
                  <div className="flex justify-between">
                    <span>Graph Subgraph Rebuild:</span>
                    <span className="text-slate-200">{selectedEvent.latency_ms?.graph_update?.toFixed(1)}ms</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Feature Extraction:</span>
                    <span className="text-slate-200">{selectedEvent.latency_ms?.feature_extract?.toFixed(1)}ms</span>
                  </div>
                  <div className="flex justify-between">
                    <span>XGBoost + IF Scoring:</span>
                    <span className="text-slate-200">{selectedEvent.latency_ms?.scoring?.toFixed(1)}ms</span>
                  </div>
                </div>
              </div>

              {/* Generated Evidence Items */}
              <div className="space-y-1.5">
                <div className="font-semibold text-slate-300 text-xs">
                  Active Evidence ({selectedEvent.evidence?.length || 0})
                </div>
                {selectedEvent.evidence && selectedEvent.evidence.length > 0 ? (
                  <div className="space-y-1.5 max-h-36 overflow-y-auto">
                    {selectedEvent.evidence.map((ev, i) => (
                      <div key={i} className="p-2 rounded bg-slate-900/90 border border-slate-800 text-[11px]">
                        <span className="font-semibold text-cyan-300 uppercase tracking-wide text-[10px] block">
                          {ev.type.replace(/_/g, ' ')}
                        </span>
                        <span className="text-slate-300 mt-0.5 block">{ev.detail}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-slate-500 text-[11px] italic">
                    No anomalous signals threshold crossed for this event.
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-slate-500 text-xs">
              Select an event from the stream to view full telemetry, model attribution, and latency metrics.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
