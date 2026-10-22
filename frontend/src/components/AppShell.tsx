"use client";

import { useEffect, useState } from "react";
import IconSidebar from "./IconSidebar";
import TopBar from "./TopBar";
import ConversationHistoryPopover from "./ConversationHistoryPopover";
import { type ViewId } from "@/lib/navigation";
import { chatActions } from "@/lib/chatStore";

const THEME_KEY = "baf.theme";

export default function AppShell({
  view, onChange, children,
}: {
  view: ViewId;
  onChange: (view: ViewId) => void;
  children: React.ReactNode;
}) {
  const [dark, setDark] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  useEffect(() => {
    const saved = window.localStorage.getItem(THEME_KEY);
    const initial = saved === "dark";
    setDark(initial);
    document.documentElement.dataset.theme = initial ? "dark" : "light";
    chatActions.hydrate();
  }, []);

  function toggleTheme() {
    setDark((current) => {
      const next = !current;
      document.documentElement.dataset.theme = next ? "dark" : "light";
      window.localStorage.setItem(THEME_KEY, next ? "dark" : "light");
      return next;
    });
  }

  return (
    <div className="relative flex h-[100dvh] w-full overflow-hidden bg-[var(--app-bg)] text-[var(--text)]">
      <IconSidebar
        view={view}
        onChange={onChange}
        dark={dark}
        onToggleTheme={toggleTheme}
        onOpenHistory={() => setHistoryOpen((open) => !open)}
      />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <TopBar
          view={view}
          onChange={onChange}
        />
        <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          {children}
        </main>
      </div>
      {historyOpen && (
        <ConversationHistoryPopover
          onClose={() => setHistoryOpen(false)}
          onChange={onChange}
        />
      )}
    </div>
  );
}
