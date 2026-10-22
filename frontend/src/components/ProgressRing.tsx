import type { CSSProperties } from "react";

const RADIUS = 19;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export default function ProgressRing({ value }: { value: number }) {
  const progress = Math.max(0, Math.min(value, 100));
  const offset = CIRCUMFERENCE * (1 - progress / 100);

  return (
    <svg
      aria-hidden="true"
      className="h-12 w-12 shrink-0 -rotate-90"
      viewBox="0 0 48 48"
      style={{
        "--ring-offset": offset,
        "--ring-circumference": CIRCUMFERENCE,
      } as CSSProperties}
    >
      <circle cx="24" cy="24" r={RADIUS} fill="none" stroke="var(--line)" strokeWidth="5" />
      <circle
        className="animated-progress-ring"
        cx="24"
        cy="24"
        r={RADIUS}
        fill="none"
        stroke="#EB0029"
        strokeLinecap="round"
        strokeWidth="5"
      />
    </svg>
  );
}
