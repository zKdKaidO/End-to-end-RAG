import { Menu } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { ProductSidebar, type ProductSidebarProps } from "./ProductSidebar";

type SidebarData = Omit<ProductSidebarProps, "expanded" | "mobile" | "onCloseMobile" | "onInteractionChange">;

export function ProductShell({ sidebar, children, rightPanel, rightOpen = false, onCloseRight }: { sidebar: SidebarData; children: ReactNode; rightPanel?: ReactNode; rightOpen?: boolean; onCloseRight?: () => void }) {
  const [expanded, setExpanded] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const interaction = useRef(false);
  const focusInside = useRef(false);
  const collapseTimer = useRef<number | null>(null);
  const mobileRef = useRef<HTMLDivElement>(null);
  const mobileTrigger = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const clearCollapse = () => { if (collapseTimer.current != null) window.clearTimeout(collapseTimer.current); collapseTimer.current = null; };
  const scheduleCollapse = useCallback(() => {
    clearCollapse();
    collapseTimer.current = window.setTimeout(() => { if (!focusInside.current && !interaction.current) setExpanded(false); }, 260);
  }, []);

  useEffect(() => () => clearCollapse(), []);
  useEffect(() => {
    if (!mobileOpen) return;
    previousFocus.current = document.activeElement as HTMLElement | null;
    const panel = mobileRef.current;
    panel?.querySelector<HTMLElement>("a,button")?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setMobileOpen(false); return; }
      if (event.key !== "Tab" || !panel) return;
      const items = Array.from(panel.querySelectorAll<HTMLElement>("a[href],button:not([disabled]),input:not([disabled])"));
      if (!items.length) return;
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", keydown);
    return () => { document.removeEventListener("keydown", keydown); previousFocus.current?.focus(); };
  }, [mobileOpen]);

  const sidebarProps = { ...sidebar, onInteractionChange: (active: boolean) => { interaction.current = active; if (active) { clearCollapse(); setExpanded(true); } else scheduleCollapse(); } };
  return <div className="lexicon-product"><div className="h-[100dvh] overflow-hidden bg-slate-50 text-slate-900">
    {(mobileOpen || rightOpen) ? <button className="fixed inset-0 z-30 hidden bg-slate-950/30 max-[1279px]:block" aria-label="Close overlay" onClick={() => { setMobileOpen(false); onCloseRight?.(); }} /> : null}
    <button ref={mobileTrigger} className="fixed left-3 top-3 z-20 hidden h-9 w-9 border-slate-200 bg-white p-0 text-slate-600 shadow-sm max-[899px]:inline-flex" aria-label="Open navigation" title="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={18} /></button>
    <div className="flex h-full min-w-0">
      <div className={`hidden h-full flex-none transition-[width] duration-200 ease-out min-[900px]:block ${expanded ? "w-[216px]" : "w-14"}`} onMouseEnter={() => { clearCollapse(); setExpanded(true); }} onMouseLeave={scheduleCollapse} onFocusCapture={() => { focusInside.current = true; clearCollapse(); setExpanded(true); }} onBlurCapture={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) { focusInside.current = false; scheduleCollapse(); } }}>
        <ProductSidebar {...sidebarProps} expanded={expanded} mobile={false} onCloseMobile={() => undefined} />
      </div>
      {mobileOpen ? <div ref={mobileRef} className="fixed inset-y-0 left-0 z-40 w-[min(280px,88vw)] min-[900px]:hidden"><ProductSidebar {...sidebarProps} expanded mobile onCloseMobile={() => setMobileOpen(false)} /></div> : null}
      <main className="min-h-0 min-w-0 flex-1">{children}</main>
      {rightPanel && rightOpen ? <div className="h-full w-[350px] flex-none max-[1279px]:fixed max-[1279px]:inset-y-0 max-[1279px]:right-0 max-[1279px]:z-40 max-[1279px]:w-[min(380px,94vw)]">{rightPanel}</div> : null}
    </div>
  </div></div>;
}
