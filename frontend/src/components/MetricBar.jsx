export default function MetricBar({ label, value, tone }) {
  const normalizedValue = typeof value === 'number' ? value : 0;
  const displayValue = typeof value === 'number' ? `${value}%` : 'No conectado';

  return (
    <div className="metric-row">
      <div className="metric-header">
        <span>{label}</span>
        <strong>{displayValue}</strong>
      </div>
      <div className="metric-track">
        <div className={`metric-fill ${tone}`} style={{ width: `${normalizedValue}%` }} />
      </div>
    </div>
  );
}
