import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { AlertCircle, CheckCircle2, Database, Eye, FileSearch, FileText, RefreshCw, Search, Trash2, Upload } from "lucide-react";
import { Drawer, EmptyState, ErrorNotice, Metric, StatusBadge } from "../components/Common";
import { DocumentDeleteDialog } from "../components/documents/DocumentDeleteDialog";
import type { DocumentFilter } from "../components/documents/documentStatus";
import { BrowserComputeClient, type LocalComputeDocument } from "../compute";
import { ProductShell } from "../components/product/ProductShell";
import type { AuthUser, DocumentPipeline } from "../types";
import "./DocumentsPage.css";

const DEFAULT_USER: AuthUser = {
  id: "standalone",
  email: "user@local",
  role: "USER",
  status: "ACTIVE",
  must_change_password: false,
};

interface DocumentsPageProps {
  user?: AuthUser;
  onLogout?: () => void;
}

type LocalJobSnapshot = {
  job_id: string;
  state: string;
  operation: string;
  document_id?: string | null;
  artifact_id?: string | null;
  stage?: string | null;
  progress?: number | null;
  error_code?: string | null;
  cancellation_requested?: boolean | number | null;
  created_at?: number | null;
  updated_at?: number | null;
};

type LocalDocument = LocalComputeDocument & {
  latest_job?: LocalJobSnapshot | null;
};

type TrackedUpload = {
  documentId: string;
  filename: string;
};

export function DocumentsPage({ user = DEFAULT_USER, onLogout = () => undefined }: DocumentsPageProps) {
  const [documents, setDocuments] = useState<LocalDocument[]>([]);
  const [selected, setSelected] = useState<LocalDocument | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<LocalDocument | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [trackedUpload, setTrackedUpload] = useState<TrackedUpload | null>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<DocumentFilter>("ALL");
  const [visibleLimit, setVisibleLimit] = useState(50);
  const [uploadAccess, setUploadAccess] = useState<"private" | "global">("private");
  const [rowAction, setRowAction] = useState<Record<string, "index" | "delete">>({});
  const [computeReady, setComputeReady] = useState(false);

  const loadInFlight = useRef(false);
  const computeRef = useRef<BrowserComputeClient | null>(null);

  if (!computeRef.current) {
    computeRef.current = new BrowserComputeClient();
  }

  const compute = computeRef.current;

  const load = useCallback(async (quiet = false) => {
    if (loadInFlight.current) return;

    loadInFlight.current = true;

    if (!quiet) {
      setLoading(true);
      setError(null);
    }

    try {
      if (!compute.status().session) {
        await compute.discover();
        await compute.connect("documents");
      }

      const nextDocuments = await compute.listDocuments() as LocalDocument[];

      setDocuments(nextDocuments);

      setSelected((current) => {
        if (!current) return current;

        return (
          nextDocuments.find(
            (document) => document.document_id === current.document_id,
          ) ?? current
        );
      });

      setComputeReady(true);
    } catch (value) {
      setComputeReady(false);

      if (!quiet) {
        setError(value);
      }

      throw value;
    } finally {
      loadInFlight.current = false;

      if (!quiet) {
        setLoading(false);
      }
    }
  }, [compute]);

  useEffect(() => {
    void load().catch(() => undefined);
  }, [load]);

  const hasActivePipeline =
    Boolean(trackedUpload) ||
    documents.some((item) => getLocalDocumentDisplayState(item).active);

  useEffect(() => {
    if (!hasActivePipeline) return;

    let stopped = false;
    let failures = 0;
    let timer: number | undefined;

    const schedule = (delay: number) => {
      timer = window.setTimeout(poll, delay);
    };

    const poll = async () => {
      if (stopped) return;

      if (window.document.visibilityState === "hidden") {
        schedule(5_000);
        return;
      }

      try {
        await load(true);
        failures = 0;
      } catch {
        failures += 1;
      }

      if (!stopped) {
        const delay =
          failures === 0
            ? 1_500
            : Math.min(
                15_000,
                1_500 * 2 ** Math.min(failures, 3),
              );

        schedule(delay);
      }
    };

    const visibility = () => {
      if (
        !stopped &&
        window.document.visibilityState === "visible"
      ) {
        if (timer) {
          window.clearTimeout(timer);
        }

        schedule(0);
      }
    };

    window.document.addEventListener(
      "visibilitychange",
      visibility,
    );

    schedule(750);

    return () => {
      stopped = true;

      if (timer) {
        window.clearTimeout(timer);
      }

      window.document.removeEventListener(
        "visibilitychange",
        visibility,
      );
    };
  }, [hasActivePipeline, load]);

  useEffect(() => {
    if (!trackedUpload) return;

    const document = documents.find(
      (item) =>
        item.document_id === trackedUpload.documentId,
    );

    if (!document) return;

    const display =
      getLocalDocumentDisplayState(document);

    const job = latestJob(document);

    if (display.key === "READY") {
      setUploadMessage(
        `${trackedUpload.filename} is ready.`,
      );

      setTrackedUpload(null);
      return;
    }

    if (display.failed) {
      const errorCode =
        job?.error_code ??
        document.last_error_code;

      setUploadMessage(
        errorCode
          ? `${trackedUpload.filename} failed: ${errorCode}.`
          : `${trackedUpload.filename} failed during processing.`,
      );

      setTrackedUpload(null);
      return;
    }

    if (job && isActiveJob(job)) {
      const stage =
        formatJobStage(job.stage);

      const progress =
        normalizeProgress(
          job.progress,
        );

      setUploadMessage(
        `${trackedUpload.filename}: ${stage} ${progress}%`,
      );
    }
  }, [documents, trackedUpload]);

  const visible = useMemo(() => {
    const term =
      search
        .trim()
        .toLocaleLowerCase("vi");

    return documents.filter((item) => {
      const searchMatches =
        !term ||
        `${item.original_filename} ${item.document_id}`
          .toLocaleLowerCase("vi")
          .includes(term);

      return (
        searchMatches &&
        matchesLocalDocumentFilter(
          item,
          filter,
        )
      );
    });
  }, [documents, filter, search]);

  const metrics = useMemo(
    () => ({
      total: documents.length,

      ready: documents.filter(
        (item) =>
          getLocalDocumentDisplayState(item).key ===
          "READY",
      ).length,

      failed: documents.filter(
        (item) =>
          getLocalDocumentDisplayState(item).failed,
      ).length,

      chunks: documents.reduce(
        (sum, item) =>
          sum + item.chunk_count,
        0,
      ),
    }),
    [documents],
  );

  const upload = async (file?: File) => {
    if (!file) return;

    setUploading(true);
    setError(null);
    setUploadMessage(
      `Uploading ${file.name}…`,
    );

    try {
      if (!computeReady) {
        throw new Error(
          "Local ZKD Compute is unavailable.",
        );
      }

      const documentId =
        crypto.randomUUID();

      await compute.uploadSource(
        documentId,
        file,
        file.name,
      );

      setUploadMessage(
        `Starting ${file.name}…`,
      );

      await compute.prepareDocument(
        documentId,
      );

      setTrackedUpload({
        documentId,
        filename: file.name,
      });

      setUploadMessage(
        `${file.name} was accepted. Processing continues in the background.`,
      );

      await load(true);
    } catch (value) {
      setUploadMessage("");
      setError(value);

      try {
        await load(true);
      } catch {
        // Preserve the original upload/pipeline error.
      }
    } finally {
      setUploading(false);
    }
  };

  const open = async (
    document: LocalDocument,
  ) => {
    setSelected(document);
  };

  const index = async (
    document: LocalDocument,
  ) => {
    setRowAction((items) => ({
      ...items,
      [document.document_id]:
        "index",
    }));

    setError(null);

    try {
      if (!computeReady) {
        throw new Error(
          "Local ZKD Compute is unavailable.",
        );
      }

      await compute.indexDocument(
        document.document_id,
      );

      await load(true);
    } catch (value) {
      setError(value);
    } finally {
      setRowAction((items) => {
        const next = {
          ...items,
        };

        delete next[
          document.document_id
        ];

        return next;
      });
    }
  };

  const remove = async () => {
    if (!deleteTarget) return;

    const target = deleteTarget;

    setRowAction((items) => ({
      ...items,
      [target.document_id]:
        "delete",
    }));

    setError(null);

    try {
      if (!computeReady) {
        throw new Error(
          "Local ZKD Compute is unavailable.",
        );
      }

      await compute.deleteDocument(
        target.document_id,
      );

      setDeleteTarget(null);

      if (
        trackedUpload?.documentId ===
        target.document_id
      ) {
        setTrackedUpload(null);
        setUploadMessage("");
      }

      setSelected((item) =>
        item?.document_id ===
        target.document_id
          ? null
          : item,
      );

      await load(true);
    } catch (value) {
      setError(value);
    } finally {
      setRowAction((items) => {
        const next = {
          ...items,
        };

        delete next[
          target.document_id
        ];

        return next;
      });
    }
  };

  return (
    <ProductShell
      user={user}
      onLogout={onLogout}
    >
      <div className="zkd-documents">
        <div className="zkd-documents-inner">
          <header className="zkd-documents-header">
            <div>
              <h1>Documents</h1>
              <p>
                Manage the sources available to zKd AI.
              </p>
            </div>

            <div className="zkd-documents-header-actions">
              {user.role === "ADMIN" ? (
                <label className="zkd-access-control">
                  <span>Access</span>

                  <select
                    aria-label="Upload access"
                    value={uploadAccess}
                    onChange={(event) =>
                      setUploadAccess(
                        event.target.value as
                          | "private"
                          | "global",
                      )
                    }
                  >
                    <option value="private">
                      Private
                    </option>

                    <option value="global">
                      Global
                    </option>
                  </select>
                </label>
              ) : null}

              <label
                className={`zkd-upload-button ${
                  uploading ||
                  !computeReady
                    ? "is-disabled"
                    : ""
                }`}
              >
                <Upload
                  size={15}
                  strokeWidth={1.9}
                />

                <span>
                  {uploading
                    ? "Uploading…"
                    : "Upload PDF"}
                </span>

                <input
                  type="file"
                  accept="application/pdf"
                  disabled={
                    uploading ||
                    !computeReady
                  }
                  onChange={(event) => {
                    const file =
                      event.target
                        .files?.[0];

                    event.currentTarget.value =
                      "";

                    void upload(file);
                  }}
                />
              </label>
            </div>
          </header>

          <section
            className="zkd-document-metrics"
            aria-label="Corpus summary"
          >
            <SummaryCard
              label="Documents"
              value={metrics.total}
              icon={
                <FileText size={17} />
              }
            />

            <SummaryCard
              label="Ready"
              value={metrics.ready}
              icon={
                <CheckCircle2
                  size={17}
                />
              }
            />

            <SummaryCard
              label="Failed"
              value={metrics.failed}
              icon={
                <AlertCircle
                  size={17}
                />
              }
              danger={
                metrics.failed > 0
              }
            />

            <SummaryCard
              label="Chunks"
              value={formatCount(
                metrics.chunks,
              )}
              icon={
                <Database size={17} />
              }
            />
          </section>

          <section
            className="zkd-document-library"
            aria-label="Document library"
          >
            <div className="zkd-document-toolbar">
              <label className="zkd-document-search">
                <Search size={15} />

                <input
                  aria-label="Search documents"
                  placeholder="Search documents..."
                  value={search}
                  onChange={(event) => {
                    setSearch(
                      event.target.value,
                    );

                    setVisibleLimit(50);
                  }}
                />
              </label>

              <select
                className="zkd-document-filter"
                aria-label="Filter documents"
                value={filter}
                onChange={(event) => {
                  setFilter(
                    event.target.value as
                      DocumentFilter,
                  );

                  setVisibleLimit(50);
                }}
              >
                <option value="ALL">
                  All statuses
                </option>

                <option value="READY">
                  Ready
                </option>

                <option value="PROCESSING">
                  Processing
                </option>

                <option value="FAILED">
                  Failed
                </option>
              </select>

              <button
                type="button"
                className="zkd-refresh-button"
                title="Refresh pipeline state"
                disabled={loading}
                onClick={() =>
                  void load().catch(
                    () => undefined,
                  )
                }
              >
                <RefreshCw
                  size={14}
                  className={
                    loading
                      ? "zkd-spin"
                      : undefined
                  }
                />

                <span>Refresh</span>
              </button>

              <span className="zkd-document-count">
                {visible.length} of{" "}
                {documents.length}
              </span>
            </div>

            <div
              className="zkd-status-legend"
              aria-label="Document status legend"
            >
              <span>
                <i className="zkd-status-dot is-ready" />
                Ready
              </span>

              <span>
                <i className="zkd-status-dot is-processing" />
                Processing
              </span>

              <span>
                <i className="zkd-status-dot is-failed" />
                Failed
              </span>
            </div>

            {uploadMessage ? (
              <div
                className="zkd-upload-message"
                role="status"
              >
                {uploadMessage}
              </div>
            ) : null}

            {error ? (
              <div className="zkd-document-error">
                <ErrorNotice
                  error={error}
                  title="Document action failed"
                />
              </div>
            ) : null}

            {loading &&
            !documents.length ? (
              <div className="zkd-document-loading">
                Loading documents…
              </div>
            ) : null}

            {!loading &&
            !visible.length ? (
              <div className="zkd-document-empty">
                <EmptyState
                  icon={
                    <FileSearch
                      size={19}
                    />
                  }
                >
                  {documents.length
                    ? "No documents match this search or filter."
                    : "No documents yet. Upload a PDF to get started."}
                </EmptyState>
              </div>
            ) : null}

            {visible.length ? (
              <div className="zkd-document-list">
                <div className="zkd-document-list-header">
                  <span>Document</span>
                  <span>Status</span>
                  <span>
                    Knowledge
                  </span>
                  <span>Added</span>
                  <span>Actions</span>
                </div>

                {visible
                  .slice(
                    0,
                    visibleLimit,
                  )
                  .map((document) => (
                    <DocumentRow
                      key={
                        document.document_id
                      }
                      document={
                        document
                      }
                      action={
                        rowAction[
                          document
                            .document_id
                        ]
                      }
                      available={
                        computeReady
                      }
                      onOpen={() =>
                        void open(
                          document,
                        )
                      }
                      onIndex={() =>
                        void index(
                          document,
                        )
                      }
                      onDelete={() =>
                        setDeleteTarget(
                          document,
                        )
                      }
                    />
                  ))}
              </div>
            ) : null}

            {visible.length >
            visibleLimit ? (
              <button
                type="button"
                className="zkd-load-more"
                onClick={() =>
                  setVisibleLimit(
                    (value) =>
                      value + 50,
                  )
                }
              >
                Load 50 more
              </button>
            ) : null}
          </section>
        </div>

        <DocumentDetail
          document={selected}
          onClose={() =>
            setSelected(null)
          }
        />

        <DocumentDeleteDialog
          document={
            deleteTarget as
              | DocumentPipeline
              | null
          }
          pending={
            deleteTarget
              ? rowAction[
                  deleteTarget
                    .document_id
                ] === "delete"
              : false
          }
          onCancel={() =>
            setDeleteTarget(null)
          }
          onConfirm={() =>
            void remove()
          }
        />
      </div>
    </ProductShell>
  );
}

function SummaryCard({
  label,
  value,
  icon,
  danger = false,
}: {
  label: string;
  value: string | number;
  icon: ReactNode;
  danger?: boolean;
}) {
  return (
    <div
      className={`zkd-document-metric ${
        danger
          ? "is-danger"
          : ""
      }`}
    >
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>

      <div className="zkd-document-metric-icon">
        {icon}
      </div>
    </div>
  );
}

function DocumentRow({
  document,
  action,
  available,
  onOpen,
  onIndex,
  onDelete,
}: {
  document: LocalDocument;
  action?: "index" | "delete";
  available: boolean;
  onOpen: () => void;
  onIndex: () => void;
  onDelete: () => void;
}) {
  const display =
    getLocalDocumentDisplayState(
      document,
    );

  const job =
    latestJob(document);

  const statusDotClass =
    display.failed
      ? "is-failed"
      : display.active
        ? "is-processing"
        : display.key === "READY"
          ? "is-ready"
          : "is-neutral";

  const pipelineText =
    job && isActiveJob(job)
      ? `${formatJobStage(
          job.stage,
        )} · ${normalizeProgress(
          job.progress,
        )}%`
      : document.index_state;

  return (
    <article className="zkd-document-row">
      <button
        type="button"
        className="zkd-document-main"
        aria-label={`Open details for ${document.original_filename}`}
        onClick={onOpen}
      >
        <span className="zkd-document-file-icon">
          <FileText size={17} />
        </span>

        <span className="zkd-document-name">
          <strong
            title={
              document.original_filename
            }
          >
            {
              document.original_filename
            }
          </strong>

          <small>
            {document.page_count ||
              "—"}{" "}
            pages ·{" "}
            {formatBytes(
              document.byte_size,
            )}
          </small>
        </span>
      </button>

      <div className="zkd-document-status">
        <span className="zkd-status-indicator">
          <i
            className={`zkd-status-dot ${statusDotClass}`}
          />

          <span>
            {display.label}
          </span>
        </span>
      </div>

      <div className="zkd-document-knowledge">
        <strong>
          {document.chunk_count}{" "}
          chunks
        </strong>

        <span>
          {pipelineText}
        </span>
      </div>

      <div className="zkd-document-date">
        {formatDate(
          document.created_at,
        )}
      </div>

      <div className="zkd-document-actions">
        <button
          type="button"
          aria-label={`Inspect ${document.original_filename}`}
          title="Inspect"
          disabled={
            Boolean(action)
          }
          onClick={onOpen}
        >
          <Eye size={15} />
        </button>

        {display.canIndex &&
        !display.failed ? (
          <button
            type="button"
            aria-label={`${display.indexActionLabel ?? "Index"} ${document.original_filename}`}
            title={
              display.indexActionLabel ??
              "Index"
            }
            disabled={
              Boolean(action) ||
              !available
            }
            onClick={onIndex}
          >
            <RefreshCw
              size={15}
              className={
                action === "index"
                  ? "zkd-spin"
                  : undefined
              }
            />
          </button>
        ) : null}

        <button
          type="button"
          className="is-danger"
          aria-label={`Delete ${document.original_filename}`}
          title="Delete document"
          disabled={
            Boolean(action) ||
            !available
          }
          onClick={onDelete}
        >
          <Trash2 size={15} />
        </button>
      </div>
    </article>
  );
}

function DocumentDetail({
  document,
  onClose,
}: {
  document: LocalDocument | null;
  onClose: () => void;
}) {
  const job = document
    ? latestJob(document)
    : null;

  return (
    <Drawer
      open={Boolean(document)}
      wide
      title={
        document?.original_filename ??
        "Document"
      }
      eyebrow="Document lineage"
      onClose={onClose}
    >
      {document ? (
        <>
          <div className="metric-grid compact">
            <Metric
              label="Pages"
              value={
                document.page_count
              }
            />

            <Metric
              label="Local state"
              value={
                document.preparation_state
              }
            />

            <Metric
              label="Chunks"
              value={
                document.chunk_count
              }
            />

            <Metric
              label="Index"
              value={
                document.index_state
              }
            />
          </div>

          <dl className="key-values">
            <dt>Document ID</dt>

            <dd className="mono">
              {document.document_id}
            </dd>

            <dt>Storage</dt>
            <dd>Local device</dd>

            <dt>MIME type</dt>
            <dd>application/pdf</dd>

            <dt>File size</dt>

            <dd>
              {formatBytes(
                document.byte_size,
              )}
            </dd>

            {job ? (
              <>
                <dt>
                  Background job
                </dt>

                <dd>
                  {formatJobStage(
                    job.stage,
                  )}{" "}
                  ·{" "}
                  {normalizeProgress(
                    job.progress,
                  )}
                  %
                </dd>
              </>
            ) : null}
          </dl>

          <div className="stage-grid">
            {localDocumentStages(
              document,
            ).map(
              ({
                label,
                ...stage
              }) => (
                <section
                  className="panel stage-card"
                  key={label}
                >
                  <span className="eyebrow">
                    {label}
                  </span>

                  <StatusBadge
                    value={
                      stage.status
                    }
                  />

                  <p>
                    {stage.current_stage ??
                      "No active stage"}
                  </p>

                  {stage.error_message ? (
                    <div className="notice error">
                      {
                        stage.error_stage
                      }
                      :{" "}
                      {
                        stage.error_message
                      }
                    </div>
                  ) : null}
                </section>
              ),
            )}
          </div>

          <div className="section-title">
            <div>
              <span className="eyebrow">
                Evidence units
              </span>

              <h2>
                Stored chunks
              </h2>
            </div>

            <span>0</span>
          </div>

          <EmptyState>
            Local document metadata
            does not expose chunk
            content.
          </EmptyState>
        </>
      ) : null}
    </Drawer>
  );
}

type LocalDocumentDisplayState = {
  key:
    | "READY"
    | "PROCESSING"
    | "PREPARED"
    | "FAILED";
  label: string;
  active: boolean;
  failed: boolean;
  canIndex: boolean;
  indexActionLabel:
    | "Index document"
    | "Re-index"
    | null;
};

function getLocalDocumentDisplayState(
  document: LocalDocument,
): LocalDocumentDisplayState {
  const preparation =
    (
      document.preparation_state ??
      ""
    )
      .trim()
      .toUpperCase();

  const index =
    (
      document.index_state ??
      ""
    )
      .trim()
      .toUpperCase();

  const job =
    latestJob(document);

  const jobState =
    (
      job?.state ??
      ""
    )
      .trim()
      .toUpperCase();

  if (
    preparation ===
      "INDEX_READY" ||
    index === "INDEX_READY"
  ) {
    return {
      key: "READY",
      label: "Ready",
      active: false,
      failed: false,
      canIndex: true,
      indexActionLabel:
        "Re-index",
    };
  }

  if (
    jobState === "FAILED"
  ) {
    return {
      key: "FAILED",
      label: "Failed",
      active: false,
      failed: true,
      canIndex: false,
      indexActionLabel: null,
    };
  }

  if (
    jobState === "CANCELLED"
  ) {
    return {
      key: "FAILED",
      label: "Cancelled",
      active: false,
      failed: true,
      canIndex: false,
      indexActionLabel: null,
    };
  }

  if (
    job &&
    isActiveJob(job)
  ) {
    const stage =
      formatJobStage(
        job.stage,
      );

    const progress =
      normalizeProgress(
        job.progress,
      );

    return {
      key: "PROCESSING",
      label: `${stage} ${progress}%`,
      active: true,
      failed: false,
      canIndex: false,
      indexActionLabel: null,
    };
  }

  if (
    preparation === "FAILED" ||
    index === "FAILED"
  ) {
    return {
      key: "FAILED",
      label: "Failed",
      active: false,
      failed: true,
      canIndex: false,
      indexActionLabel: null,
    };
  }

  if (
    preparation ===
      "PREPARED_NOT_INDEXED" ||
    index === "NOT_INDEXED"
  ) {
    return {
      key: "PREPARED",
      label: "Prepared",
      active: false,
      failed: false,
      canIndex: true,
      indexActionLabel:
        "Index document",
    };
  }

  if (
    preparation === "INDEXING" ||
    index === "INDEXING"
  ) {
    return {
      key: "PROCESSING",
      label: "Indexing",
      active: true,
      failed: false,
      canIndex: false,
      indexActionLabel: null,
    };
  }

  return {
    key: "PROCESSING",
    label: "Processing",
    active: true,
    failed: false,
    canIndex: false,
    indexActionLabel: null,
  };
}

function matchesLocalDocumentFilter(
  document: LocalDocument,
  filter: DocumentFilter,
): boolean {
  const state =
    getLocalDocumentDisplayState(
      document,
    );

  if (filter === "ALL") {
    return true;
  }

  if (filter === "READY") {
    return (
      state.key === "READY"
    );
  }

  if (filter === "FAILED") {
    return state.failed;
  }

  return state.active;
}

function localDocumentStages(
  document: LocalDocument,
) {
  const error =
    document.last_error_code ??
    undefined;

  const job =
    latestJob(document);

  const jobState =
    job?.state ??
    undefined;

  const jobStage =
    job
      ? formatJobStage(
          job.stage,
        )
      : undefined;

  const jobProgress =
    job
      ? normalizeProgress(
          job.progress,
        )
      : undefined;

  return [
    {
      label: "Source",
      status: "LOCAL",
      current_stage:
        "Stored on this device",
    },
    {
      label: "Preparation",
      status:
        document.preparation_state,
      current_stage:
        job &&
        isPreparationStage(
          job.stage,
        )
          ? `${jobStage} · ${jobProgress}%`
          : document.preparation_state,
      error_stage:
        error
          ? "LOCAL"
          : undefined,
      error_message: error,
    },
    {
      label: "Indexing",
      status:
        document.index_state,
      current_stage:
        job &&
        isIndexingStage(
          job.stage,
        )
          ? `${jobStage} · ${jobProgress}%`
          : jobState === "QUEUED"
            ? "Queued"
            : document.index_state,
      error_stage:
        error
          ? "LOCAL"
          : undefined,
      error_message: error,
    },
  ];
}

function latestJob(
  document: LocalDocument,
): LocalJobSnapshot | null {
  return (
    document.latest_job ??
    null
  );
}

function isActiveJob(
  job: LocalJobSnapshot,
): boolean {
  const state =
    job.state
      .trim()
      .toUpperCase();

  return (
    state === "QUEUED" ||
    state === "RUNNING" ||
    state ===
      "CANCEL_REQUESTED"
  );
}

function isPreparationStage(
  stage?: string | null,
): boolean {
  const value =
    (
      stage ??
      ""
    ).toUpperCase();

  return [
    "ACCEPTED",
    "STARTING",
    "RECOVERING",
    "EXTRACTING",
    "CLEANING",
    "RECONSTRUCTING",
    "PARSING",
    "CHUNKING",
    "PERSISTING",
    "VALIDATING",
    "PREPARED_NOT_INDEXED",
  ].includes(value);
}

function isIndexingStage(
  stage?: string | null,
): boolean {
  const value =
    (
      stage ??
      ""
    ).toUpperCase();

  return [
    "LOADING_EMBEDDING_MODEL",
    "INDEXING",
    "VALIDATING_INDEX",
    "INDEX_READY",
  ].includes(value);
}

function formatJobStage(
  stage?: string | null,
): string {
  const value =
    (
      stage ??
      "PROCESSING"
    )
      .trim()
      .toUpperCase();

  const labels: Record<
    string,
    string
  > = {
    ACCEPTED: "Queued",
    STARTING: "Starting",
    RECOVERING: "Recovering",
    EXTRACTING: "Extracting",
    CLEANING: "Cleaning",
    RECONSTRUCTING:
      "Reconstructing",
    PARSING: "Parsing",
    CHUNKING: "Chunking",
    PERSISTING: "Saving",
    VALIDATING: "Validating",
    PREPARED_NOT_INDEXED:
      "Prepared",
    LOADING_EMBEDDING_MODEL:
      "Loading model",
    INDEXING: "Indexing",
    VALIDATING_INDEX:
      "Validating index",
    INDEX_READY: "Ready",
    FAILED: "Failed",
    CANCELLED: "Cancelled",
  };

  if (labels[value]) {
    return labels[value];
  }

  return value
    .toLocaleLowerCase()
    .replaceAll("_", " ")
    .replace(
      /\b\w/g,
      (character) =>
        character.toUpperCase(),
    );
}

function normalizeProgress(
  progress?: number | null,
): number {
  if (
    typeof progress !== "number" ||
    !Number.isFinite(progress)
  ) {
    return 0;
  }

  return Math.max(
    0,
    Math.min(
      100,
      Math.round(progress),
    ),
  );
}

function formatDate(
  value?: number | null,
) {
  return value
    ? new Intl.DateTimeFormat(
        undefined,
        {
          dateStyle: "medium",
        },
      ).format(
        new Date(
          value * 1_000,
        ),
      )
    : "—";
}

function formatCount(
  value: number,
) {
  return new Intl.NumberFormat().format(
    value,
  );
}

function formatBytes(
  value: number,
) {
  if (!value) return "0 B";

  const units = [
    "B",
    "KB",
    "MB",
    "GB",
  ];

  const unit = Math.min(
    Math.floor(
      Math.log(value) /
        Math.log(1024),
    ),
    units.length - 1,
  );

  return `${(
    value /
    1024 ** unit
  ).toFixed(
    unit ? 1 : 0,
  )} ${units[unit]}`;
}