"use client";

import { useEffect, useState } from "react";

const currency = new Intl.NumberFormat("es-MX", {
  style: "currency",
  currency: "MXN",
  maximumFractionDigits: 0,
});

export function formatAnimatedAmount(value: number) {
  return currency.format(value);
}

export default function AnimatedAmount({ value }: { value: number }) {
  const [displayed, setDisplayed] = useState(0);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;
    let start: number | null = null;
    const duration = 800;

    function animate(time: number) {
      if (start === null) start = time;
      const progress = Math.min((time - start) / duration, 1);
      const eased = 1 - (1 - progress) ** 3;
      setDisplayed(value * eased);
      if (progress < 1) frame = requestAnimationFrame(animate);
    }

    const startAnimation = () => {
      cancelAnimationFrame(frame);
      if (media.matches) {
        setDisplayed(value);
        return;
      }
      start = null;
      frame = requestAnimationFrame(animate);
    };

    startAnimation();
    media.addEventListener("change", startAnimation);
    return () => {
      cancelAnimationFrame(frame);
      media.removeEventListener("change", startAnimation);
    };
  }, [value]);

  return (
    <>
      <span aria-hidden="true">{formatAnimatedAmount(displayed)}</span>
      <span className="sr-only">{formatAnimatedAmount(value)}</span>
    </>
  );
}
