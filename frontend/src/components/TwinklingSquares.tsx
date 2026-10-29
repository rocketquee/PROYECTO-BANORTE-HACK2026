"use client";

import { useEffect, useRef } from "react";

type Direction = "left" | "right" | "up" | "down";

type TwinklingSquaresProps = {
  direction?: Direction;
  gridCells?: number;
  squareSize?: number;
  fadeStart?: number;
  fadeEnd?: number;
  fadeCurve?: number;
  minBrightness?: number;
  blinkSpeed?: number;
  blinkStrength?: number;
  intensity?: number;
  opacity?: number;
  color?: string;
  backgroundColor?: string;
  maxDpr?: number;
};

function randomAt(x: number, y: number, salt: number) {
  const value = Math.sin(x * 127.1 + y * 311.7 + salt * 74.7) * 43758.5453;
  return value - Math.floor(value);
}

export default function TwinklingSquares({
  direction = "right",
  gridCells = 52,
  squareSize = 0.57,
  fadeStart = 0.33,
  fadeEnd = 1,
  fadeCurve = 1.25,
  minBrightness = 0.55,
  blinkSpeed = 1.4,
  blinkStrength = 0.94,
  intensity = 1,
  opacity = 1,
  color = "var(--squares-color)",
  backgroundColor = "#000000",
  maxDpr = 1.5,
}: TwinklingSquaresProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const canvasElement = canvas;
    const maybeContext = canvasElement.getContext("2d");
    if (!maybeContext) return;
    const context = maybeContext;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let frameId: number | null = null;
    let width = 0;
    let height = 0;
    let elapsed = 0;
    let resolvedColor = color;

    function resolveColor() {
      const variable = /^var\(\s*(--[\w-]+)\s*(?:,\s*([^)]+))?\s*\)$/.exec(color);
      if (!variable) {
        resolvedColor = color;
        return;
      }

      resolvedColor = getComputedStyle(document.documentElement)
        .getPropertyValue(variable[1])
        .trim() || variable[2]?.trim() || "#EB0029";
    }
    resolveColor();

    function draw(time: number) {
      elapsed = time / 1000;

      const bounds = canvasElement.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, maxDpr);
      if (bounds.width !== width || bounds.height !== height || canvasElement.width !== Math.round(bounds.width * dpr) || canvasElement.height !== Math.round(bounds.height * dpr)) {
        width = bounds.width;
        height = bounds.height;
        canvasElement.width = Math.round(width * dpr);
        canvasElement.height = Math.round(height * dpr);
      }
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      context.globalAlpha = 1;
      context.fillStyle = backgroundColor;
      context.fillRect(0, 0, width, height);

      const cellSize = Math.max(1, Math.max(width, height) / Math.max(1, gridCells));
      const columns = Math.ceil(width / cellSize);
      const rows = Math.ceil(height / cellSize);
      const square = cellSize * squareSize;
      const fadeRange = Math.max(0.001, fadeEnd - fadeStart);

      context.fillStyle = resolvedColor;
      for (let row = 0; row < rows; row += 1) {
        for (let column = 0; column < columns; column += 1) {
          let distanceFromDenseEdge: number;
          if (direction === "right") distanceFromDenseEdge = 1 - (column + 0.5) / columns;
          else if (direction === "left") distanceFromDenseEdge = (column + 0.5) / columns;
          else if (direction === "down") distanceFromDenseEdge = 1 - (row + 0.5) / rows;
          else distanceFromDenseEdge = (row + 0.5) / rows;

          const fadeProgress = Math.min(1, Math.max(0, (distanceFromDenseEdge - fadeStart) / fadeRange));
          const density = Math.pow(1 - fadeProgress, fadeCurve);
          const positionRandom = randomAt(column, row, 1);
          if (positionRandom > density) continue;

          const phase = randomAt(column, row, 2) * Math.PI * 2;
          const speedVariation = 0.8 + randomAt(column, row, 3) * 0.4;
          const pulse = (Math.sin(elapsed * blinkSpeed * speedVariation + phase) + 1) / 2;
          const brightness = minBrightness + (1 - minBrightness) * (
            1 - blinkStrength + blinkStrength * pulse
          );
          context.globalAlpha = Math.min(1, Math.max(0, density * brightness * intensity * opacity));
          context.fillRect(
            column * cellSize + (cellSize - square) / 2,
            row * cellSize + (cellSize - square) / 2,
            square,
            square
          );
        }
      }
      context.globalAlpha = 1;
    }

    function stop() {
      if (frameId !== null) {
        cancelAnimationFrame(frameId);
        frameId = null;
      }
    }

    function animate(time: number) {
      frameId = null;
      if (document.hidden) return;
      draw(time);
      if (!reducedMotion.matches) frameId = requestAnimationFrame(animate);
    }

    function start() {
      if (!document.hidden && frameId === null) {
        if (reducedMotion.matches) draw(0);
        else frameId = requestAnimationFrame(animate);
      }
    }

    function handleMotionChange() {
      stop();
      if (reducedMotion.matches) draw(0);
      else start();
    }

    function handleVisibilityChange() {
      if (document.hidden) stop();
      else start();
    }

    const resizeObserver = new ResizeObserver(() => {
      draw(elapsed * 1000);
    });
    const themeObserver = new MutationObserver(() => {
      resolveColor();
      draw(elapsed * 1000);
    });
    resizeObserver.observe(canvasElement);
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    reducedMotion.addEventListener("change", handleMotionChange);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    draw(0);
    start();

    return () => {
      stop();
      resizeObserver.disconnect();
      themeObserver.disconnect();
      reducedMotion.removeEventListener("change", handleMotionChange);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [
    backgroundColor,
    blinkSpeed,
    blinkStrength,
    color,
    direction,
    fadeCurve,
    fadeEnd,
    fadeStart,
    gridCells,
    intensity,
    maxDpr,
    minBrightness,
    opacity,
    squareSize,
  ]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 h-full w-full"
    />
  );
}
