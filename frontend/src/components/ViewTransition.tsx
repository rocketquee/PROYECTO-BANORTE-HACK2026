"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

type Snapshot = { view: string; children: ReactNode };

export default function ViewTransition({
  view,
  children,
}: {
  view: string;
  children: ReactNode;
}) {
  const previous = useRef<Snapshot>({ view, children });
  const [outgoing, setOutgoing] = useState<Snapshot | null>(null);
  const viewport = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (previous.current.view !== view) {
      setOutgoing(previous.current);
      if (viewport.current) viewport.current.scrollTop = 0;
    }
    previous.current = { view, children };
  }, [view, children]);

  useEffect(() => {
    if (!outgoing) return;
    const timeout = window.setTimeout(() => setOutgoing(null), 150);
    return () => window.clearTimeout(timeout);
  }, [outgoing]);

  return (
    <div ref={viewport} className="h-full min-h-0 overflow-y-auto">
      <div className="relative min-h-full">
        {outgoing && (
          <div
            key={`outgoing-${outgoing.view}`}
            aria-hidden="true"
            inert
            className="absolute inset-0 z-10 min-h-full animate-screen-exit"
          >
            {outgoing.children}
          </div>
        )}
        <div
          key={`incoming-${view}`}
          className="relative z-20 min-h-full animate-screen-enter"
        >
          {children}
        </div>
      </div>
    </div>
  );
}
