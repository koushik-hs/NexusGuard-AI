type Band = 'Critical' | 'High' | 'Medium' | 'Low';
import { AnimatedNumber } from './AnimatedNumber';

interface Props {
  band: Band;
  score?: number;
  showScore?: boolean;
}

const BAND_CLASS: Record<Band, string> = {
  Critical: 'critical',
  High:     'high',
  Medium:   'medium',
  Low:      'low',
};

const BAND_DOT: Record<Band, string> = {
  Critical: '#6b4f3a',
  High:     '#7d6048',
  Medium:   '#987b5e',
  Low:      '#52705a',
};

export function RiskBadge({ band, score, showScore = false }: Props) {
  return (
    <span className={`risk-badge ${BAND_CLASS[band] || 'low'}`}>
      <span style={{
        width: 5,
        height: 5,
        borderRadius: '50%',
        background: BAND_DOT[band],
        display: 'inline-block',
        flexShrink: 0,
      }} />
      {band}
      {showScore && score !== undefined && (
        <span style={{ fontFamily: 'var(--font-mono)', marginLeft: 4 }}>
          <AnimatedNumber value={score} decimals={0} />
        </span>
      )}
    </span>
  );
}

interface ScoreBarProps {
  score: number;
  band: Band;
}

const BAND_COLOR: Record<Band, string> = {
  Critical: '#6b4f3a',
  High:     '#7d6048',
  Medium:   '#987b5e',
  Low:      '#52705a',
};

export function ScoreBar({ score, band }: ScoreBarProps) {
  return (
    <div className="score-bar-wrap">
      <div className="score-bar">
        <div
          className="score-bar-fill"
          style={{ width: `${score}%`, background: BAND_COLOR[band] }}
        />
      </div>
      <span className="score-value">{score.toFixed(0)}</span>
    </div>
  );
}
