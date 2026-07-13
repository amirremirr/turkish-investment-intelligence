// Zero-JS server-rendered line chart (an SVG path). No client bundle.

export function Sparkline({
  points,
  width = 640,
  height = 200,
  stroke = "var(--accent)",
}: {
  points: number[];
  width?: number;
  height?: number;
  stroke?: string;
}) {
  if (points.length < 2) return null;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const pad = 6;
  const w = width - pad * 2;
  const h = height - pad * 2;

  const coords = points.map((p, i) => {
    const x = pad + (i / (points.length - 1)) * w;
    const y = pad + h - ((p - min) / range) * h;
    return [x, y] as const;
  });

  const path = coords
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" ");
  const area =
    `M${coords[0][0].toFixed(1)},${(height - pad).toFixed(1)} ` +
    coords.map(([x, y]) => `L${x.toFixed(1)},${y.toFixed(1)}`).join(" ") +
    ` L${coords[coords.length - 1][0].toFixed(1)},${(height - pad).toFixed(1)} Z`;

  const up = points[points.length - 1] >= points[0];
  const color = stroke;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      preserveAspectRatio="none"
      role="img"
      aria-label="price history"
    >
      <path d={area} fill={color} opacity={0.08} />
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
        opacity={up ? 1 : 0.9}
      />
    </svg>
  );
}
