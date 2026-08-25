import { useEffect, useRef } from "react";
import type { DocumentPipeline } from "../../types";

export function DocumentDeleteDialog({ document, pending, onCancel, onConfirm }: { document: DocumentPipeline | null; pending: boolean; onCancel: () => void; onConfirm: () => void }) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const pendingRef = useRef(pending);
  const cancelAction = useRef(onCancel);
  pendingRef.current = pending;
  cancelAction.current = onCancel;
  useEffect(() => {
    if (!document) return;
    previousFocus.current = documentElement();
    cancelRef.current?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !pendingRef.current) { event.preventDefault(); cancelAction.current(); return; }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const controls = Array.from(dialogRef.current.querySelectorAll<HTMLElement>("button:not([disabled])"));
      if (!controls.length) return;
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && window.document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && window.document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.document.addEventListener("keydown", keydown);
    return () => { window.document.removeEventListener("keydown", keydown); previousFocus.current?.focus(); };
  }, [document?.document_id]);
  if (!document) return null;
  return <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/40 p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !pending) onCancel(); }}>
    <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="delete-document-title" className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
      <h2 id="delete-document-title" className="m-0 text-base font-semibold text-slate-900">Remove “{document.filename}”?</h2>
      <p className="mt-3 text-sm leading-6 text-slate-600">Remove this document from your private library. Derived data is deleted only when no other private or global access remains; shared/global access may keep it visible.</p>
      <div className="mt-5 flex justify-end gap-2"><button ref={cancelRef} className="border-slate-200 bg-white px-4 py-2 text-sm text-slate-700" disabled={pending} onClick={onCancel}>Cancel</button><button className="border-red-600 bg-red-600 px-4 py-2 text-sm font-semibold text-white" disabled={pending} onClick={onConfirm}>{pending ? "Removing…" : "Remove"}</button></div>
    </div>
  </div>;
}

function documentElement() { return window.document.activeElement as HTMLElement | null; }
