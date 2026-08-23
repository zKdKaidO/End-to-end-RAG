export type Json = Record<string, unknown>;

export interface PipelineStage {
  status: string;
  current_stage?: string | null;
  error_stage?: string | null;
  error_type?: string | null;
  error_message?: string | null;
}

export interface ChunkDetail {
  chunk_id: string;
  document_id: string;
  legal_unit_id?: string | null;
  content_text: string;
  embedding_text: string;
  metadata_json: Json;
  provenance_json: Json;
  page_start: number;
  page_end: number;
}

export interface DocumentPipeline {
  document_id: string;
  filename: string;
  mime_type: string;
  file_size: number;
  created_at?: string | null;
  updated_at?: string | null;
  ingestion: PipelineStage;
  processing: PipelineStage;
  indexing: PipelineStage;
  page_count: number;
  legal_unit_count: number;
  chunk_count: number;
  index_count: number;
  chunks?: ChunkDetail[];
  access_origin?: "PRIVATE" | "GLOBAL" | "PRIVATE + GLOBAL";
}

export interface AuthUser {
  id: string;
  email: string;
  role: "USER" | "ADMIN";
  status: "ACTIVE" | "DISABLED" | "DELETING";
  must_change_password: boolean;
}

export interface Candidate {
  chunk_id: string;
  document_id: string;
  dense_rank?: number | null;
  dense_score?: number | null;
  lexical_rank?: number | null;
  lexical_score?: number | null;
  fusion_score?: number | null;
  final_rank?: number | null;
  retrieval_final_rank?: number | null;
  context_candidate_order?: number | null;
  candidate_origin?: "RETRIEVAL" | "HIERARCHY_CHILD" | null;
  legal_unit_id?: string | null;
  hierarchy_relation?: "DIRECT_CHILD" | null;
  hierarchy_depth?: number | null;
  anchor_chunk_id?: string | null;
  anchor_legal_unit_id?: string | null;
  anchor_retrieval_final_rank?: number | null;
  hierarchy_anchor_references?: Json[];
  content_preview: string;
  content_text?: string | null;
  metadata_json?: Json | null;
  provenance_json?: Json | null;
}

export interface SelectedEvidence {
  source_id: string;
  retrieval_final_rank: number | null;
  context_candidate_order: number;
  candidate_origin: "RETRIEVAL" | "HIERARCHY_CHILD";
  legal_unit_id?: string | null;
  hierarchy_relation?: "DIRECT_CHILD" | null;
  hierarchy_depth: number;
  anchor_chunk_id?: string | null;
  anchor_legal_unit_id?: string | null;
  anchor_retrieval_final_rank?: number | null;
  chunk_id: string;
  document_id: string;
  token_count: number;
  content_text: string;
  metadata_json: Json;
  provenance_json: Json;
  dense_rank?: number | null;
  lexical_rank?: number | null;
  fusion_score: number | null;
}

export interface Citation {
  source_id: string;
  chunk_id: string;
  document_id: string;
  metadata_json: Json;
  provenance_json: Json;
  retrieval_final_rank?: number | null;
  snapshot_id?: string;
  citation_order?: number;
  original_legal_unit_id?: string | null;
  document_title?: string | null;
  document_filename?: string | null;
  document_sha256?: string | null;
  chunk_content_sha256?: string;
  page_start?: number | null;
  page_end?: number | null;
  article?: string | null;
  clause?: string | null;
  point?: string | null;
  evidence_text?: string;
  availability?: "CURRENT_EQUIVALENT" | "SOURCE_UPDATED" | "SOURCE_UNAVAILABLE";
  current_document_id?: string | null;
  current_chunk_id?: string | null;
}

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
  last_message_preview: string | null;
  message_count: number;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  turn_id: string;
  role: "USER" | "ASSISTANT";
  sequence_no: number;
  content: string;
  delivery_state: "COMMITTED" | "STREAMING" | "COMPLETED" | "FAILED" | "CANCELLED";
  answer_status: "ANSWERABLE" | "INSUFFICIENT_EVIDENCE" | null;
  model_id: string | null;
  prompt_version: string | null;
  created_at: string;
  finalized_at: string | null;
  failure_code: string | null;
  failure_detail_safe: string | null;
  citations: Citation[];
}

export interface GenerationResult {
  request_id: string;
  status: string;
  answer_text: string;
  citations: Citation[];
  invalid_citations: string[];
  citation_validation: string;
  model_id: string;
  prompt_version: string;
  finish_reason?: string | null;
  usage?: Json | null;
  answerability_status?: string | null;
  answerability_validation: string;
}

export interface DebugTrace {
  request_id: string;
  query_text: string;
  document_ids: string[];
  retrieval: {
    dense_candidates: Candidate[];
    lexical_candidates: Candidate[];
    final_candidates: Candidate[];
    rrf_candidates: Candidate[];
    hierarchy_candidates: Candidate[];
    final_context_candidates: Candidate[];
    hierarchy: Record<string, unknown>;
    dense_candidate_count: number;
    lexical_candidate_count: number;
    overlap_count: number;
    lexical_mode: string;
    score_semantics: string;
    timings_ms: Record<string, number>;
  };
  context: {
    candidate_count: number;
    duplicate_count: number;
    selected_count: number;
    dropped_count: number;
    context_token_count: number;
    context_budget_tokens: number;
    budget_utilization_percent: number;
    budget_exhausted: boolean;
    stop_reason: string;
    selected_evidence: SelectedEvidence[];
  };
  generation: Omit<GenerationResult, "request_id"> & {
    prompt_token_count: number;
    context_token_count: number;
    generation_ms?: number | null;
    time_to_first_token_ms?: number | null;
  };
  timings_ms: Record<string, number>;
  expected?: {
    case_id: string;
    category: string;
    answerable: boolean;
    expected_document_ids: string[];
    acceptable_evidence_sets: string[][];
    source_reference?: string | null;
    notes?: string | null;
  } | null;
  diagnosis?: string | null;
}

export interface EvaluationCase {
  case_id: string;
  category: string;
  question: string;
  answerable: boolean;
  retrieval_result: string;
  context_result: string;
  generation_result: string;
  diagnosis: string;
}

export interface EvaluationSummary {
  report_id: string;
  dataset_sha256: string;
  aggregate: EvaluationAggregate;
  known_limitations: string[];
}

export interface EvaluationComparison {
  before: EvaluationAggregate;
  after: EvaluationAggregate;
  delta: Json;
  known_limitations: string[];
}

export interface EvaluationAggregate {
  case_count?: number;
  answerable_count?: number;
  unanswerable_count?: number;
  failure_counts?: Record<string, number>;
  retrieval?: {
    hit_at_1?: number;
    hit_at_3?: number;
    hit_at_5?: number;
    hit_at_10?: number;
    mrr?: number;
  };
  context?: { expected_evidence_retention?: number };
  generation?: {
    citation_presence_rate?: number;
    citation_structural_validity_rate?: number;
    expected_source_citation_match_rate?: number;
    missing_citation_rate?: number;
    invalid_citation_rate?: number;
  };
  unanswerable?: {
    correct_abstention_rate?: number;
    unsupported_answer_rate?: number;
  };
}
