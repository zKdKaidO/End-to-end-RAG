import { BookOpen, Edit3, LogOut, MessageSquarePlus, Search, Trash2, X } from "lucide-react";
import { NavLink } from "react-router-dom";
import type { AuthUser, ChatSession } from "../../types";

export interface ProductSidebarProps {
  user: AuthUser;
  expanded: boolean;
  mobile: boolean;
  sessions?: ChatSession[];
  activeSessionId?: string | null;
  hasOlderSessions?: boolean;
  onSelectSession?: (id: string) => void;
  onCreateSession?: () => void | Promise<void>;
  onRenameSession?: (session: ChatSession) => void | Promise<void>;
  onDeleteSession?: (session: ChatSession) => void | Promise<void>;
  onLoadOlderSessions?: () => void;
  onLogout: () => void;
  onCloseMobile: () => void;
  onInteractionChange: (active: boolean) => void;
}

export function ProductSidebar(props: ProductSidebarProps) {
  const { expanded, mobile, sessions, activeSessionId, user } = props;
  const showLabels = expanded || mobile;
  const runInteraction = async (action: () => void | Promise<void>) => {
    props.onInteractionChange(true);
    try { await action(); } finally { props.onInteractionChange(false); }
  };
  return (
    <aside className="flex h-full flex-col overflow-hidden border-r border-slate-200 bg-white" aria-label="Product navigation" data-expanded={showLabels}>
      <div className="flex h-16 flex-none items-center gap-3 border-b border-slate-100 px-3">
        <span className="grid h-8 w-8 flex-none place-items-center rounded-md bg-blue-600 text-sm font-bold text-white" aria-hidden="true">L</span>
        <div className={`min-w-0 flex-1 whitespace-nowrap transition-opacity ${showLabels ? "opacity-100" : "pointer-events-none opacity-0"}`}><strong className="block text-sm text-blue-700">Lexicon AI</strong><small className="block text-[10px] text-slate-500">Legal Counsel</small></div>
        {mobile ? <button className="border-0 bg-transparent p-1 text-slate-500" aria-label="Close navigation" title="Close navigation" onClick={props.onCloseMobile}><X size={17} /></button> : null}
      </div>
      <nav className="space-y-1 px-2 py-4" aria-label="Product areas">
        <NavLink to="/ask" title="Search" className={({ isActive }) => `flex h-9 items-center gap-3 rounded-md px-3 text-xs font-semibold no-underline ${isActive ? "bg-blue-50 text-blue-700" : "text-slate-500 hover:bg-slate-50 hover:text-slate-800"}`}><Search size={15} className="flex-none" /><span className={`whitespace-nowrap transition-opacity ${showLabels ? "opacity-100" : "pointer-events-none opacity-0"}`}>Search</span></NavLink>
        <NavLink to="/documents" title="Library" className={({ isActive }) => `flex h-9 items-center gap-3 rounded-md px-3 text-xs font-semibold no-underline ${isActive ? "bg-blue-50 text-blue-700" : "text-slate-500 hover:bg-slate-50 hover:text-slate-800"}`}><BookOpen size={15} className="flex-none" /><span className={`whitespace-nowrap transition-opacity ${showLabels ? "opacity-100" : "pointer-events-none opacity-0"}`}>Library</span></NavLink>
      </nav>
      {sessions ? <section className={`flex min-h-0 flex-1 flex-col border-t border-slate-100 px-2 py-3 transition-opacity ${showLabels ? "opacity-100" : "pointer-events-none invisible opacity-0"}`} aria-label="Recent inquiries">
        <div className="mb-2 flex items-center justify-between px-1"><span className="whitespace-nowrap text-[10px] font-semibold uppercase tracking-wider text-slate-400">Recent inquiries</span><button className="border-0 bg-transparent p-1 text-blue-600" aria-label="New Inquiry" title="New Inquiry" onClick={() => void runInteraction(() => props.onCreateSession?.())}><MessageSquarePlus size={16} /></button></div>
        <div className="min-h-0 flex-1 space-y-1 overflow-y-auto">
          {sessions.map((session) => <div key={session.id} className={`group grid grid-cols-[minmax(0,1fr)_24px_24px] items-center rounded-md ${session.id === activeSessionId ? "bg-blue-50" : "hover:bg-slate-50"}`}>
            <button className={`min-w-0 justify-start overflow-hidden border-0 bg-transparent px-2 py-2 text-left text-xs ${session.id === activeSessionId ? "font-semibold text-blue-700" : "text-slate-600"}`} onClick={() => props.onSelectSession?.(session.id)}><span className="block truncate">{session.title}</span></button>
            <button className="border-0 bg-transparent p-1 text-slate-400 hover:text-slate-700" aria-label={`Rename ${session.title}`} title={`Rename ${session.title}`} onClick={() => void runInteraction(() => props.onRenameSession?.(session))}><Edit3 size={12} /></button>
            <button className="border-0 bg-transparent p-1 text-slate-400 hover:text-red-600" aria-label={`Delete ${session.title}`} title={`Delete ${session.title}`} onClick={() => void runInteraction(() => props.onDeleteSession?.(session))}><Trash2 size={12} /></button>
          </div>)}
        </div>
        {props.hasOlderSessions ? <button className="mt-2 w-full border-slate-200 bg-white px-2 py-2 text-xs text-slate-600" onClick={props.onLoadOlderSessions}>Older conversations</button> : null}
      </section> : <div className="flex-1" />}
      <div className="border-t border-slate-200 p-2">
        <button className="flex w-full justify-start gap-3 border-0 bg-transparent px-2 py-2 text-slate-600 hover:bg-slate-50" title={showLabels ? "Sign out" : `${user.email} — expand account`} aria-label={showLabels ? "Sign out" : `Account ${user.email}`} onClick={showLabels ? props.onLogout : undefined}>
          <span className="grid h-7 w-7 flex-none place-items-center rounded-full bg-slate-100 text-[10px] font-bold text-slate-600">{user.email.slice(0, 1).toUpperCase()}</span>
          <span className={`min-w-0 flex-1 text-left transition-opacity ${showLabels ? "opacity-100" : "pointer-events-none opacity-0"}`}><strong className="block truncate text-xs">{user.email}</strong><small className="block text-[9px] uppercase text-slate-400">{user.role}</small></span>
          {showLabels ? <LogOut size={14} className="self-center" /> : null}
        </button>
      </div>
    </aside>
  );
}
