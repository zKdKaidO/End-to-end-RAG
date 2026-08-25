import { PanelRight } from "lucide-react";
import type { ReactNode } from "react";
import { ScopeBadge } from "./ScopeBadge";

export function ChatWorkspace({ title, scopeLabel, feed, composer, onOpenScope, onOpenEvidence }: {
  title: string;
  scopeLabel: string;
  feed: ReactNode;
  composer: ReactNode;
  onOpenScope: () => void;
  onOpenEvidence: () => void;
}) {
  return (
    <section className="flex h-full min-h-0 flex-col bg-white" aria-label="Legal research chat">
      <header className="flex h-16 flex-none items-center gap-3 border-b border-slate-200 px-4 sm:px-6">
        <span className="w-8 flex-none min-[900px]:hidden" aria-hidden="true" />
        <div className="min-w-0 flex-1"><h1 className="m-0 truncate text-sm font-semibold text-slate-900">{title}</h1></div>
        <ScopeBadge label={scopeLabel} onClick={onOpenScope} />
        <button className="border-0 bg-transparent p-1 text-slate-500" aria-label="Open evidence panel" onClick={onOpenEvidence}><PanelRight size={18} /></button>
      </header>
      <div className="min-h-0 flex-1">{feed}</div>
      <div className="flex-none">{composer}</div>
    </section>
  );
}
