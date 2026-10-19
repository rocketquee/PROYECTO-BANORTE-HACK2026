"use client";

import { useReducer, useState } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardView from "@/components/DashboardView";
import AgentView from "@/components/AgentView";

export default function Home() {
  const [view, setView] = useState<"dashboard" | "asistente">("asistente");
  const [refreshKey, bumpRefresh] = useReducer((x: number) => x + 1, 0);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar view={view} onChange={setView} />
      <main className="min-w-0 flex-1 overflow-y-auto">
        {view === "dashboard" ? (
          <DashboardView refreshKey={refreshKey} />
        ) : (
          <AgentView onGoalsChanged={bumpRefresh} />
        )}
      </main>
    </div>
  );
}
