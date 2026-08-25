import { Search, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { CitationSummary, EmptyState, SourceList } from "../Common";
import type { Citation, DocumentPipeline } from "../../types";
import { SourceDocumentCard } from "./SourceDocumentCard";

export type SourcePanelTab = "scope" | "evidence";

export function SourcePanel({ tab, onTabChange, documents, selectedDocumentIds, activeCitation, evidenceCitations, onToggleDocument, onSelectAll, onSelectCitation, onOpenCitationDetail, onClose }: {
  tab: SourcePanelTab;
  onTabChange: (tab: SourcePanelTab) => void;
  documents: DocumentPipeline[];
  selectedDocumentIds: string[];
  activeCitation: Citation | null;
  evidenceCitations: Citation[];
  onToggleDocument: (documentId: string) => void;
  onSelectAll: () => void;
  onSelectCitation: (citation: Citation) => void;
  onOpenCitationDetail: (citation: Citation) => void;
  onClose: () => void;
}) {
  const [search, setSearch] = useState("");
  const [limit, setLimit] = useState(50);
  const indexed = useMemo(() => documents.filter((item) => item.index_count > 0), [documents]);
  const filtered = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("vi");
    return term ? indexed.filter((item) => item.filename.toLocaleLowerCase("vi").includes(term)) : indexed;
  }, [indexed, search]);
  const allSelected = indexed.length > 0 && selectedDocumentIds.length === indexed.length && indexed.every((item) => selectedDocumentIds.includes(item.document_id));
  useEffect(() => {
    if (tab !== "evidence" || !activeCitation) return;
    window.document.getElementById(`source-${activeCitation.source_id}`)?.scrollIntoView?.({ block: "nearest" });
  }, [activeCitation, tab]);
  return <aside className="flex h-full flex-col border-l border-slate-200 bg-slate-50" aria-label="Source panel">
    <header className="flex h-16 flex-none items-center justify-between border-b border-slate-200 px-4"><div><span className="block text-[10px] font-semibold uppercase tracking-wider text-blue-700">Source panel</span><small className="text-[10px] text-slate-500">Referenced materials</small></div><button className="border-0 bg-transparent p-1 text-slate-500" aria-label="Close source panel" onClick={onClose}><X size={17} /></button></header>
    <div className="grid grid-cols-2 border-b border-slate-200 bg-white p-1" role="tablist" aria-label="Source panel mode">
      {(["scope", "evidence"] as const).map((value) => <button key={value} role="tab" aria-selected={tab === value} className={`border-0 px-3 py-2 text-xs font-semibold capitalize ${tab === value ? "bg-blue-50 text-blue-700" : "bg-transparent text-slate-500"}`} onClick={() => onTabChange(value)}>{value}</button>)}
    </div>
    <div className="min-h-0 flex-1 overflow-y-auto p-3">
      {tab === "scope" ? <section aria-labelledby="research-scope-heading">
        <div className="mb-2 flex items-center justify-between"><h2 id="research-scope-heading" className="m-0 text-xs font-semibold text-slate-800">Research Scope</h2><label className="flex cursor-pointer items-center gap-1.5 text-[10px] font-medium text-blue-600"><input type="checkbox" className="h-3.5 w-3.5 accent-blue-600" aria-label="Select All" checked={allSelected} onChange={onSelectAll} />Select All</label></div>
        <label className="mb-3 flex items-center gap-2 rounded-md border border-slate-200 bg-white px-2"><Search size={13} className="text-slate-400"/><span className="sr-only">Search scope documents</span><input className="h-8 border-0 bg-transparent p-0 text-xs shadow-none outline-none" aria-label="Search scope documents" placeholder="Search documents" value={search} onChange={(event) => { setSearch(event.target.value); setLimit(50); }} /></label>
        <div className="space-y-2">{filtered.slice(0, limit).map((document) => <SourceDocumentCard key={document.document_id} document={document} selected={selectedDocumentIds.includes(document.document_id)} onToggle={onToggleDocument} />)}</div>
        {!filtered.length ? <EmptyState>{indexed.length ? "No indexed documents match this search." : "No indexed documents are available."}</EmptyState> : null}
        {filtered.length > limit ? <button className="mt-3 w-full border-slate-200 bg-white px-3 py-2 text-xs text-blue-700" onClick={() => setLimit((value) => value + 50)}>Load 50 more</button> : null}
      </section> : <section aria-labelledby="cited-evidence-heading">
        <h2 id="cited-evidence-heading" className="mb-2 text-xs font-semibold text-slate-800">Cited Evidence</h2>
        {activeCitation ? <><CitationSummary citation={activeCitation} />{activeCitation.evidence_text ? <p className="rounded-lg border border-slate-200 bg-white p-3 text-xs leading-5 text-slate-600">{activeCitation.evidence_text}</p> : null}<button className="mb-3 mt-2 w-full border-slate-200 bg-white px-3 py-2 text-xs text-blue-700" onClick={() => onOpenCitationDetail(activeCitation)}>Open evidence detail</button></> : <p className="text-xs leading-5 text-slate-500">Select a citation in an answer to inspect its immutable evidence snapshot.</p>}
        {evidenceCitations.length ? <SourceList citations={evidenceCitations} activeSourceId={activeCitation?.source_id} onInspect={onSelectCitation} /> : null}
      </section>}
    </div>
  </aside>;
}
