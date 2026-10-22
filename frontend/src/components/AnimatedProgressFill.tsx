export default function AnimatedProgressFill({
  value,
  className,
}: {
  value: number;
  className: string;
}) {
  const clamped = Math.max(0, Math.min(value, 100));

  return (
    <div
      aria-hidden="true"
      className={`animated-progress-fill h-full origin-left rounded-full ${className}`}
      style={{ "--progress-scale": clamped / 100 } as React.CSSProperties}
    />
  );
}
