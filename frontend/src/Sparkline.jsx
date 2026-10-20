// Tiny dependency-free SVG line chart.
export default function Sparkline({ points, up }) {
  const values = points.map((p) => p.close).filter((v) => v != null);
  if (values.length < 2) return <div className="spark spark-empty">No history</div>;

  const w = 240;
  const h = 56;
  const pad = 4;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const x = (i) => pad + (i / (values.length - 1)) * (w - pad * 2);
  const y = (v) => h - pad - ((v - min) / range) * (h - pad * 2);

  const line = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const area = `${line} L${x(values.length - 1).toFixed(1)},${h} L${x(0).toFixed(1)},${h} Z`;
  const color = up ? "var(--up)" : "var(--down)";

  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" role="img"
         aria-label={`30-day price trend, ${up ? "rising" : "falling"}`}>
      <path d={area} fill={color} opacity="0.12" />
      <path d={line} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
