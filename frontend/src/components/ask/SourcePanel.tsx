import { useMemo, useState } from "react";
import { Search, X } from "lucide-react";
import type { LocalCitation } from "../../compute";

export type SourcePanelTab = "scope" | "evidence";

export interface SourcePanelDocument {
  document_id: string;
  filename: string;
  page_count: number;
  chunk_count: number;
}

interface SourcePanelProps {
  tab: SourcePanelTab;
  onTabChange: (tab: SourcePanelTab) => void;
  documents: SourcePanelDocument[];
  selectedDocumentIds: string[];
  activeCitation: LocalCitation | null;
  evidenceCitations: LocalCitation[];
  onToggleDocument: (documentId: string) => void;
  onSelectAll: () => void;
  onSelectCitation: (citation: LocalCitation) => void;
  onOpenCitationDetail: (citation: LocalCitation) => void;
  onClose: () => void;
}

function safePage(value: unknown): string | null {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0 ? String(value) : null;
}

function documentMeta(item: SourcePanelDocument) {
  return `${item.page_count} pages · ${item.chunk_count} chunks`;
}

export function SourcePanel({ tab, onTabChange, documents, selectedDocumentIds, activeCitation, evidenceCitations, onToggleDocument, onSelectAll, onSelectCitation, onOpenCitationDetail, onClose }: SourcePanelProps) {
  const [search, setSearch] = useState("");
  const filteredDocuments = useMemo(() => {
    const keyword = search.trim().toLocaleLowerCase();
    return keyword ? documents.filter((item) => item.filename.toLocaleLowerCase().includes(keyword)) : documents;
  }, [documents, search]);
  const allSelected = documents.length > 0 && documents.every((item) => selectedDocumentIds.includes(item.document_id));

  return <section className="source-panel-root" aria-label="Source panel">
    <div className="source-panel-top"><div><h2>Sources</h2><p>Referenced materials</p></div><button type="button" className="source-panel-close" aria-label="Close sources" onClick={onClose}><X size={16} /></button></div>
    <div className="source-panel-tabs" role="tablist" aria-label="Source panel mode">
      <button type="button" role="tab" aria-selected={tab === "scope"} className={`source-panel-tab ${tab === "scope" ? "is-active" : ""}`} onClick={() => onTabChange("scope")}>Scope</button>
      <button type="button" role="tab" aria-selected={tab === "evidence"} className={`source-panel-tab ${tab === "evidence" ? "is-active" : ""}`} onClick={() => onTabChange("evidence")}>Evidence</button>
    </div>
    {tab === "scope" ? <>
      <div className="source-scope-header"><strong>Sources</strong><button type="button" className={`scope-select-all ${allSelected ? "is-selected" : ""}`} onClick={onSelectAll}><span className="source-choice-control" aria-hidden="true" /><span>Select all</span></button></div>
      <label className="source-search"><Search size={15} /><input type="search" value={search} placeholder="Search sources" aria-label="Search scope documents" onChange={(event) => setSearch(event.target.value)} /></label>
      <div className="source-card-list">{filteredDocuments.length === 0 ? <div className="source-empty-state">No sources match this search.</div> : filteredDocuments.map((item) => {
        const selected = selectedDocumentIds.includes(item.document_id);
        return <button key={item.document_id} type="button" className={`source-card ${selected ? "is-selected" : ""}`} onClick={() => onToggleDocument(item.document_id)}><span className="source-choice-control" aria-hidden="true" /><span className="source-card-copy"><strong title={item.filename}>{item.filename}</strong><small>{documentMeta(item)}</small></span></button>;
      })}</div>
    </> : <div className="evidence-card-list">
      {evidenceCitations.length === 0 ? <div className="source-empty-state">No evidence selected yet.</div> : evidenceCitations.map((citation) => {
        const active = activeCitation?.source_id === citation.source_id && activeCitation?.chunk_id === citation.chunk_id;
        const page = safePage(citation.provenance_json.page_start) ?? safePage(citation.provenance_json.page_end);
        const filename = documents.find((item) => item.document_id === citation.document_id)?.filename;
        return <button key={`${citation.source_id}-${citation.chunk_id}`} type="button" className={`evidence-card ${active ? "is-active" : ""}`} onClick={() => onSelectCitation(citation)} onDoubleClick={() => onOpenCitationDetail(citation)}><div className="evidence-card-head"><strong>{citation.source_id}</strong><span>{page ? `Page ${page}` : filename ?? citation.document_id}</span></div><p>Evidence preview is unavailable locally.</p></button>;
      })}
    </div>}
  </section>;
}
