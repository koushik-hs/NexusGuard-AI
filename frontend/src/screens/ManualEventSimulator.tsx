import React, { useState } from 'react';
import { api } from '../api/client';
import type { LiveUpdate } from '../api/client';
import { RiskBadge } from '../components/RiskBadge';
import {
  Send,
  Sparkles,
  ShieldCheck,
  ShieldAlert,
  Layers,
  History,
} from 'lucide-react';

export function ManualEventSimulator() {
  const [buyerId, setBuyerId] = useState('MAN_BUYER_01');
  const [merchantId, setMerchantId] = useState('MAN_MERCH_01');
  const [amount, setAmount] = useState('8500');
  const [txnType, setTxnType] = useState<'purchase' | 'refund'>('purchase');
  const [deviceId, setDeviceId] = useState('DEV_MAN_A');
  const [ipId, setIpId] = useState('IP_MAN_A');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [lastResult, setLastResult] = useState<LiveUpdate | null>(null);
  const [submissionHistory, setSubmissionHistory] = useState<LiveUpdate[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setErrorMsg(null);
    setIsSubmitting(true);

    try {
      const res = await api.submitEvent({
        buyer_id: buyerId.trim(),
        merchant_id: merchantId.trim(),
        amount: parseFloat(amount) || 100,
        txn_type: txnType,
        device_id: deviceId.trim() || undefined,
        ip_id: ipId.trim() || undefined,
        source: 'manual_simulator',
      });

      setLastResult(res);
      setSubmissionHistory((prev) => [res, ...prev.slice(0, 9)]);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to process event');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Preset scenarios to help a judge test hypotheses quickly
  const loadPreset = (type: 'normal' | 'step1' | 'step2' | 'step3' | 'circular' | 'refund') => {
    if (type === 'normal') {
      setBuyerId('LEGIT_USER_' + Math.floor(Math.random() * 900 + 100));
      setMerchantId('STORE_CENTRAL');
      setAmount('1250');
      setTxnType('purchase');
      setDeviceId('DEV_USER_' + Math.floor(Math.random() * 900 + 100));
      setIpId('IP_HOME_' + Math.floor(Math.random() * 900 + 100));
    } else if (type === 'step1') {
      setBuyerId('RING_ACCT_1');
      setMerchantId('TARGET_MERCHANT_X');
      setAmount('15000');
      setTxnType('purchase');
      setDeviceId('HARDWARE_DEV_FARM_99');
      setIpId('IP_DATACENTER_PROXY_77');
    } else if (type === 'step2') {
      setBuyerId('RING_ACCT_2');
      setMerchantId('TARGET_MERCHANT_X');
      setAmount('15200');
      setTxnType('purchase');
      setDeviceId('HARDWARE_DEV_FARM_99'); // Same device
      setIpId('IP_DATACENTER_PROXY_77'); // Same IP
    } else if (type === 'step3') {
      setBuyerId('RING_ACCT_3');
      setMerchantId('TARGET_MERCHANT_X');
      setAmount('14800');
      setTxnType('purchase');
      setDeviceId('HARDWARE_DEV_FARM_99'); // Same device
      setIpId('IP_DATACENTER_PROXY_77'); // Same IP
    } else if (type === 'circular') {
      setBuyerId('RING_ACCT_1');
      setMerchantId('RING_ACCT_2');
      setAmount('25000');
      setTxnType('purchase');
      setDeviceId('HARDWARE_DEV_FARM_99');
      setIpId('IP_DATACENTER_PROXY_77');
    } else if (type === 'refund') {
      setBuyerId('RING_ACCT_2');
      setMerchantId('TARGET_MERCHANT_X');
      setAmount('15000');
      setTxnType('refund');
      setDeviceId('HARDWARE_DEV_FARM_99');
      setIpId('IP_DATACENTER_PROXY_77');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center space-x-3">
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-cyan-400" />
            Interactive Manual Event Simulator
          </h1>
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-950 text-cyan-300 border border-cyan-800">
            Judge Evaluation Tool
          </span>
        </div>
        <p className="text-sm text-slate-400 mt-1">
          Submit individual synthetic payment events with customized telemetry. Every event flows through the identical live graph, feature extraction, and XGBoost pipeline.
        </p>
      </div>

      {/* Preset Action Strip */}
      <div className="card p-4 bg-slate-900/90 border-slate-800 space-y-2">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Quick-Load Demo Test Cases:
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => loadPreset('normal')}
            className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 border border-slate-700 transition"
          >
            1. Normal Independent Event
          </button>
          <button
            type="button"
            onClick={() => loadPreset('step1')}
            className="px-3 py-1.5 rounded bg-cyan-950 hover:bg-cyan-900 text-xs text-cyan-300 border border-cyan-800 transition"
          >
            2. Coordinated Step 1: Account A1 on Device D1
          </button>
          <button
            type="button"
            onClick={() => loadPreset('step2')}
            className="px-3 py-1.5 rounded bg-indigo-950 hover:bg-indigo-900 text-xs text-indigo-300 border border-indigo-800 transition"
          >
            3. Coordinated Step 2: Account A2 on same Device D1
          </button>
          <button
            type="button"
            onClick={() => loadPreset('step3')}
            className="px-3 py-1.5 rounded bg-purple-950 hover:bg-purple-900 text-xs text-purple-300 border border-purple-800 transition"
          >
            4. Coordinated Step 3: Account A3 on same Device D1
          </button>
          <button
            type="button"
            onClick={() => loadPreset('circular')}
            className="px-3 py-1.5 rounded bg-amber-950 hover:bg-amber-900 text-xs text-amber-300 border border-amber-800 transition"
          >
            5. Circular Transfer (A1 → A2)
          </button>
          <button
            type="button"
            onClick={() => loadPreset('refund')}
            className="px-3 py-1.5 rounded bg-rose-950 hover:bg-rose-900 text-xs text-rose-300 border border-rose-800 transition"
          >
            6. Elevated Refund Event
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Manual Form */}
        <div className="card p-6 space-y-4">
          <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
            <Send className="h-4 w-4 text-cyan-400" />
            Submit Event Telemetry
          </h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1">
                  Buyer Account ID *
                </label>
                <input
                  type="text"
                  value={buyerId}
                  onChange={(e) => setBuyerId(e.target.value)}
                  required
                  placeholder="e.g. A0101"
                  className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-cyan-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1">
                  Merchant Account ID *
                </label>
                <input
                  type="text"
                  value={merchantId}
                  onChange={(e) => setMerchantId(e.target.value)}
                  required
                  placeholder="e.g. M001"
                  className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-cyan-500 font-mono"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1">
                  Amount (INR) *
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  required
                  placeholder="8500.00"
                  className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-cyan-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1">
                  Transaction Type
                </label>
                <select
                  value={txnType}
                  onChange={(e) => setTxnType(e.target.value as any)}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-cyan-500"
                >
                  <option value="purchase">Standard Purchase</option>
                  <option value="refund">Refund Transaction</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1">
                  Client Hardware Device ID
                </label>
                <input
                  type="text"
                  value={deviceId}
                  onChange={(e) => setDeviceId(e.target.value)}
                  placeholder="e.g. D0012 or DEV_XYZ"
                  className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-cyan-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1">
                  Client Inbound IP ID
                </label>
                <input
                  type="text"
                  value={ipId}
                  onChange={(e) => setIpId(e.target.value)}
                  placeholder="e.g. IP0045 or 192.168.1.1"
                  className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-cyan-500 font-mono"
                />
              </div>
            </div>

            {errorMsg && (
              <div className="p-3 rounded bg-rose-950/60 border border-rose-800 text-rose-300 text-xs">
                {errorMsg}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full btn-primary flex items-center justify-center gap-2 py-2.5 text-sm font-semibold disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <div className="h-4 w-4 border-2 border-slate-900 border-t-transparent rounded-full animate-spin" />
                  Running Live Detection Pipeline...
                </>
              ) : (
                <>
                  <Send className="h-4 w-4" />
                  Submit Event into Pipeline
                </>
              )}
            </button>
          </form>
        </div>

        {/* Live Response & Risk Evolution Inspector */}
        <div className="card p-6 space-y-4">
          <h2 className="text-base font-bold text-slate-100 flex items-center justify-between border-b border-slate-800 pb-3">
            <span className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-cyan-400" />
              Pipeline Inference Output
            </span>
            {lastResult && (
              <RiskBadge score={lastResult.risk_score} band={lastResult.risk_band} />
            )}
          </h2>

          {lastResult ? (
            <div className="space-y-4">
              {/* Alert Status Banner */}
              <div
                className={`p-3.5 rounded border flex items-start gap-3 ${
                  lastResult.alert_triggered
                    ? 'bg-rose-950/60 border-rose-800 text-rose-200'
                    : 'bg-emerald-950/40 border-emerald-800/60 text-emerald-200'
                }`}
              >
                {lastResult.alert_triggered ? (
                  <ShieldAlert className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
                ) : (
                  <ShieldCheck className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
                )}
                <div>
                  <div className="font-bold text-xs">
                    {lastResult.alert_triggered
                      ? 'FRAUD RING ALERT TRIGGERED'
                      : 'NO ANOMALY ALERT — BENIGN EVALUATION'}
                  </div>
                  <div className="text-xs opacity-90 mt-0.5 font-mono">
                    Score: {lastResult.risk_score.toFixed(1)} / 100 | Delta:{' '}
                    {lastResult.risk_delta > 0
                      ? `+${lastResult.risk_delta.toFixed(1)}`
                      : lastResult.risk_delta.toFixed(1)}
                  </div>
                </div>
              </div>

              {/* Latency Breakdown */}
              <div className="bg-slate-900 p-3 rounded border border-slate-800 text-xs font-mono space-y-1">
                <div className="text-slate-400 font-semibold mb-1 flex justify-between">
                  <span>Actual Measured Processing Time:</span>
                  <span className="text-emerald-400">{lastResult.latency_ms?.total?.toFixed(1)}ms</span>
                </div>
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>Graph Rebuild: {lastResult.latency_ms?.graph_update?.toFixed(1)}ms</span>
                  <span>Features: {lastResult.latency_ms?.feature_extract?.toFixed(1)}ms</span>
                  <span>Inference: {lastResult.latency_ms?.scoring?.toFixed(1)}ms</span>
                </div>
              </div>

              {/* Model Attribution Breakdown */}
              <div className="bg-slate-900 p-3.5 rounded border border-slate-800 space-y-2">
                <div className="text-xs font-bold text-slate-300">Model Scores for Affected Cluster</div>
                <div className="grid grid-cols-3 gap-2 text-center text-xs font-mono">
                  <div className="bg-slate-800/80 p-2 rounded">
                    <div className="text-[10px] text-slate-400 uppercase">XGBoost</div>
                    <div className="text-cyan-400 font-bold text-sm mt-0.5">
                      {lastResult.cluster_stats?.xgb_score !== undefined &&
                      lastResult.cluster_stats.xgb_score !== null
                        ? `${(lastResult.cluster_stats.xgb_score * 100).toFixed(1)}%`
                        : 'N/A'}
                    </div>
                  </div>
                  <div className="bg-slate-800/80 p-2 rounded">
                    <div className="text-[10px] text-slate-400 uppercase">IF Anomaly</div>
                    <div className="text-indigo-400 font-bold text-sm mt-0.5">
                      {lastResult.cluster_stats?.if_score !== undefined
                        ? `${(lastResult.cluster_stats.if_score * 100).toFixed(1)}%`
                        : '0%'}
                    </div>
                  </div>
                  <div className="bg-slate-800/80 p-2 rounded">
                    <div className="text-[10px] text-slate-400 uppercase">Rule Signals</div>
                    <div className="text-amber-400 font-bold text-sm mt-0.5">
                      {lastResult.cluster_stats?.rule_score !== undefined
                        ? `${(lastResult.cluster_stats.rule_score * 100).toFixed(1)}%`
                        : '0%'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Triggered Evidence */}
              <div>
                <div className="text-xs font-bold text-slate-300 mb-1.5">Corroborating Evidence Items</div>
                {lastResult.evidence && lastResult.evidence.length > 0 ? (
                  <div className="space-y-1.5 max-h-32 overflow-y-auto">
                    {lastResult.evidence.map((ev, i) => (
                      <div key={i} className="p-2 rounded bg-slate-900 border border-slate-800 text-xs">
                        <span className="text-cyan-300 font-semibold uppercase text-[10px] block">
                          {ev.type.replace(/_/g, ' ')}
                        </span>
                        <span className="text-slate-300 mt-0.5 block text-[11px]">{ev.detail}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-xs text-slate-500 italic p-2 bg-slate-900/40 rounded">
                    No suspicious signal threshold breached.
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="p-12 text-center text-slate-500 text-xs">
              Fill the form on the left or click a demo preset to submit your first event and observe the live risk output.
            </div>
          )}
        </div>
      </div>

      {/* Recent Submission Session History */}
      {submissionHistory.length > 0 && (
        <div className="card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <History className="h-4 w-4 text-cyan-400" />
              Recent Simulator Submission Trajectory
            </h3>
            <span className="text-xs text-slate-500">{submissionHistory.length} events this session</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse font-mono">
              <thead className="bg-slate-900 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-2 px-3">Time</th>
                  <th className="py-2 px-3">Buyer → Merchant</th>
                  <th className="py-2 px-3">Amount</th>
                  <th className="py-2 px-3">Device / IP</th>
                  <th className="py-2 px-3">Risk Score</th>
                  <th className="py-2 px-3">Delta</th>
                  <th className="py-2 px-3 text-right">Alert</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {submissionHistory.map((ev, i) => (
                  <tr key={i} className="hover:bg-slate-800/40">
                    <td className="py-2 px-3 text-slate-400">
                      {new Date(ev.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="py-2 px-3 text-slate-200">
                      {ev.buyer_id} → {ev.merchant_id}
                    </td>
                    <td className="py-2 px-3 text-slate-200">₹{ev.amount.toLocaleString()}</td>
                    <td className="py-2 px-3 text-slate-400 text-[11px]">
                      {ev.device_id || '—'} / {ev.ip_id || '—'}
                    </td>
                    <td className="py-2 px-3 font-bold text-cyan-400">{ev.risk_score.toFixed(1)}</td>
                    <td
                      className={`py-2 px-3 ${
                        ev.risk_delta > 0
                          ? 'text-rose-400'
                          : ev.risk_delta < 0
                          ? 'text-emerald-400'
                          : 'text-slate-500'
                      }`}
                    >
                      {ev.risk_delta > 0 ? `+${ev.risk_delta.toFixed(1)}` : ev.risk_delta.toFixed(1)}
                    </td>
                    <td className="py-2 px-3 text-right">
                      {ev.alert_triggered ? (
                        <span className="text-rose-400 font-bold text-[10px]">ALERT</span>
                      ) : (
                        <span className="text-slate-500 text-[10px]">OK</span>
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
  );
}
