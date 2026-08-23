import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ChevronLeft, X, Info } from 'lucide-react';
import ForceGraph2D from 'react-force-graph-2d';
import { api } from '../api/client';
import type { GraphData, GraphNode, GraphEdge, RingListItem } from '../api/client';
import { RiskBadge } from '../components/RiskBadge';

// Color scheme for nodes
const NODE_COLORS: Record<string, string> = {
  account_merchant: '#1d4ed8',
  account_buyer:    '#475569',
  device:           '#b45309',
  ip_range:         '#0f766e',
};

const NODE_LABELS: Record<string, string> = {
  account_merchant: 'Merchant',
  account_buyer:    'Buyer',
  device:           'Device',
  ip_range:         'IP Range',
};

function nodeColor(node: GraphNode): string {
  if (node.node_type === 'account') {
    return NODE_COLORS[`account_${node.account_type}`] || '#475569';
  }
  return NODE_COLORS[node.node_type] || '#334155';
}

function nodeLabel(node: GraphNode): string {
  if (node.node_type === 'account') return node.id;
  if (node.node_type === 'device') return node.id;
  if (node.node_type === 'ip_range') return node.ip_range || node.id;
  return node.id;
}

interface FGNode extends GraphNode {
  x?: number;
  y?: number;
  __selected?: boolean;
}

interface FGLink extends GraphEdge {
  id: string;
}

export function GraphExplorer() {
  const { ringId: paramRingId } = useParams<{ ringId: string }>();
  const navigate = useNavigate();

  const [rings, setRings]         = useState<RingListItem[]>([]);
  const [selectedRing, setSelectedRing] = useState<string>(paramRingId || '');
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [selectedNode, setSelectedNode] = useState<FGNode | null>(null);
  const [loading, setLoading]     = useState(false);
  const graphRef = useRef<any>(null);

  // Load ring list
  useEffect(() => {
    api.listRings().then(r => {
      setRings(r);
      if (!selectedRing && r.length > 0) setSelectedRing(r[0].ring_id);
    });
  }, []);

  // Load graph when ring changes
  useEffect(() => {
    if (!selectedRing) return;
    setLoading(true);
    setSelectedNode(null);
    api.getRingGraph(selectedRing)
      .then(setGraphData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [selectedRing]);

  // Build force-graph data
  const fgData = React.useMemo(() => {
    if (!graphData) return { nodes: [], links: [] };
    const nodes: FGNode[] = graphData.nodes.map(n => ({ ...n }));
    const nodeIds = new Set(nodes.map(n => n.id));
    const links: FGLink[] = graphData.edges
      .filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
      .map((e, i) => ({ ...e, id: `e-${i}` }));
    return { nodes, links };
  }, [graphData]);

  const handleNodeClick = useCallback((node: FGNode) => {
    setSelectedNode(prev => prev?.id === node.id ? null : node);
    graphRef.current?.centerAt(node.x, node.y, 500);
  }, []);

  const paintNode = useCallback((node: FGNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const isSelected = selectedNode?.id === node.id;
    const radius = node.node_type === 'account' ? 7 : 5;
    const color = nodeColor(node);

    // Glow for selected
    if (isSelected) {
      ctx.beginPath();
      ctx.arc(node.x!, node.y!, radius + 5, 0, 2 * Math.PI);
      ctx.fillStyle = `${color}40`;
      ctx.fill();
    }

    ctx.beginPath();
    ctx.arc(node.x!, node.y!, radius, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();

    // Border
    ctx.beginPath();
    ctx.arc(node.x!, node.y!, radius, 0, 2 * Math.PI);
    ctx.strokeStyle = isSelected ? '#fff' : `${color}99`;
    ctx.lineWidth = isSelected ? 2 : 1;
    ctx.stroke();

    // Label
    const fontSize = Math.max(10 / globalScale, 2.5);
    ctx.font = `${fontSize}px JetBrains Mono, monospace`;
    ctx.fillStyle = isSelected ? '#e8edf5' : '#8fa3c0';
    ctx.textAlign = 'center';
    ctx.fillText(nodeLabel(node as GraphNode), node.x!, node.y! + radius + fontSize + 1);
  }, [selectedNode]);

  const linkColor = useCallback((link: FGLink) => {
    if (link.suspicious) {
      return link.shared_via ? '#dc2626cc' : '#ea580ccc';
    }
    return '#1e2d45';
  }, []);

  const linkWidth = useCallback((link: FGLink) => link.suspicious ? 2 : 1, []);

  const selectedRingInfo = rings.find(r => r.ring_id === selectedRing);

  return (
    <div className="graph-layout">
      {/* Canvas */}
      <div className="graph-canvas-wrap">
        {loading && (
          <div style={{
            position: 'absolute', inset: 0, display: 'flex',
            alignItems: 'center', justifyContent: 'center',
            background: 'rgba(10,15,30,0.8)', zIndex: 20,
          }}>
            <div className="spinner" />
          </div>
        )}

        {fgData.nodes.length > 0 && (
          <ForceGraph2D
            ref={graphRef}
            graphData={fgData}
            nodeCanvasObject={paintNode as any}
            nodeCanvasObjectMode={() => 'replace'}
            linkColor={linkColor as any}
            linkWidth={linkWidth as any}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={1}
            linkCurvature={0.1}
            onNodeClick={handleNodeClick as any}
            backgroundColor="#0a0f1e"
            linkLabel={(link: any) => link.edge_type}
            nodeLabel=""
            cooldownTicks={100}
            d3VelocityDecay={0.3}
          />
        )}

        {/* Legend */}
        <div className="graph-legend">
          <div className="legend-title">Legend</div>
          {Object.entries(NODE_COLORS).map(([key, color]) => (
            <div key={key} className="legend-item">
              <div className="legend-dot" style={{ background: color }} />
              {NODE_LABELS[key] || key}
            </div>
          ))}
          <div className="legend-item" style={{ marginTop: 4 }}>
            <div className="legend-line" style={{ background: '#dc2626', borderTop: '2px dashed #dc2626' }} />
            Suspicious Link
          </div>
          <div className="legend-item">
            <div className="legend-line" style={{ background: '#1e2d45' }} />
            Transaction
          </div>
        </div>

        {fgData.nodes.length === 0 && !loading && (
          <div className="empty-state" style={{ height: '100%' }}>
            <Info size={28} color="var(--text-muted)" />
            <span className="text-muted">Select a ring to view its graph</span>
          </div>
        )}
      </div>

      {/* Sidebar */}
      <div className="graph-sidebar">
        <div className="graph-sidebar-header">
          <span>Ring Selector</span>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => navigate('/')}
          >
            <ChevronLeft size={12} /> Overview
          </button>
        </div>

        <div className="ring-selector">
          {rings.map(ring => (
            <div
              key={ring.ring_id}
              id={`graph-ring-${ring.ring_id}`}
              className={`ring-selector-item ${selectedRing === ring.ring_id ? 'active' : ''}`}
              onClick={() => setSelectedRing(ring.ring_id)}
            >
              <div>
                <div className="text-mono" style={{ fontSize: 12 }}>{ring.ring_id}</div>
                <div className="text-xs text-muted">{ring.account_count} accounts</div>
              </div>
              <RiskBadge band={ring.risk_band} score={ring.risk_score} showScore />
            </div>
          ))}
        </div>

        {/* Selected ring info */}
        {selectedRingInfo && (
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
            <div className="node-detail-row">
              <span className="node-detail-label">Nodes</span>
              <span className="node-detail-value">{fgData.nodes.length}</span>
            </div>
            <div className="node-detail-row">
              <span className="node-detail-label">Links</span>
              <span className="node-detail-value">{fgData.links.length}</span>
            </div>
            <div className="node-detail-row">
              <span className="node-detail-label">Suspicious</span>
              <span className="node-detail-value" style={{ color: 'var(--risk-critical)' }}>
                {fgData.links.filter((l: FGLink) => l.suspicious).length}
              </span>
            </div>
          </div>
        )}

        {/* Node detail */}
        {selectedNode ? (
          <div className="node-detail">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="text-xs text-muted" style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Node Details
              </span>
              <button
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 4 }}
                onClick={() => setSelectedNode(null)}
              >
                <X size={12} />
              </button>
            </div>
            <div className="node-detail-row">
              <span className="node-detail-label">ID</span>
              <span className="node-detail-value">{selectedNode.id}</span>
            </div>
            <div className="node-detail-row">
              <span className="node-detail-label">Type</span>
              <span className="node-detail-value">{selectedNode.node_type}</span>
            </div>
            {selectedNode.account_type && (
              <div className="node-detail-row">
                <span className="node-detail-label">Role</span>
                <span className="node-detail-value">{selectedNode.account_type}</span>
              </div>
            )}
            {selectedNode.ip_range && (
              <div className="node-detail-row">
                <span className="node-detail-label">IP Range</span>
                <span className="node-detail-value">{selectedNode.ip_range}</span>
              </div>
            )}
            <div className="node-detail-row">
              <span className="node-detail-label">In Ring</span>
              <span className="node-detail-value" style={{ color: 'var(--risk-critical)' }}>
                {selectedNode.in_ring ? 'Yes' : 'No'}
              </span>
            </div>
          </div>
        ) : (
          <div className="empty-state" style={{ padding: 24 }}>
            <span className="text-xs text-muted">Click a node to inspect it</span>
          </div>
        )}

        {/* View investigation */}
        {selectedRing && (
          <div style={{ marginTop: 'auto', padding: '12px 16px', borderTop: '1px solid var(--border)' }}>
            <button
              id="go-to-investigation-btn"
              className="btn btn-primary"
              style={{ width: '100%', justifyContent: 'center' }}
              onClick={() => navigate(`/ring/${selectedRing}`)}
            >
              View Full Investigation
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
