import { Plus } from "lucide-react";

export function ChatComposer({ query, pending, scopeValid, onQueryChange, onSubmit, onOpenScope }: {
  query: string;
  pending: boolean;
  scopeValid: boolean;
  onQueryChange: (value: string) => void;
  onSubmit: () => void;
  onOpenScope: () => void;
}) {
  const disabled = !query.trim() || pending || !scopeValid;
  return (
    <div className="border-t border-slate-100 bg-white px-4 pb-3 pt-3 sm:px-6">
      <div className="mx-auto max-w-3xl rounded-xl border border-slate-200 bg-white shadow-sm focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100">
        <label className="sr-only" htmlFor="legal-query">Question</label>
        <textarea id="legal-query" className="min-h-20 resize-none border-0 bg-transparent px-4 py-3 text-sm text-slate-900 shadow-none outline-none placeholder:text-slate-400 focus:border-0 focus:shadow-none" value={query} onChange={(event) => onQueryChange(event.target.value)} onKeyDown={(event) => { if ((event.metaKey || event.ctrlKey) && event.key === "Enter") onSubmit(); }} rows={3} placeholder="Enter your legal query here..." />
        <div className="flex items-center justify-between border-t border-slate-100 px-3 py-2">
          <button className="gap-1 border-0 bg-transparent px-2 py-1.5 text-xs text-slate-600 hover:bg-slate-50" onClick={onOpenScope}><Plus size={13} />Add Scope</button>
          <button className="rounded-md border-blue-600 bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-700" onClick={onSubmit} disabled={disabled}>Submit</button>
        </div>
      </div>
      {!scopeValid ? <p className="mb-0 mt-2 text-center text-xs text-amber-700">Select at least one source.</p> : null}
      <p className="mb-0 mt-2 text-center text-[10px] text-slate-400">AI-generated content may require independent verification.</p>
    </div>
  );
}
