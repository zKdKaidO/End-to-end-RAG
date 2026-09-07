import { binaryBodyBytes, canonicalTranscript, createBrowserNonce, exactArrayBuffer, hmacSha256Hex, serializeJsonOnce, sha256Hex } from "./crypto";
import { BrowserComputeError, isDeviceInvalidatingCode, isSessionInvalidatingCode } from "./errors";
import {
  PlatformComputeApi,
  type AnswerRequestPreparationDiagnostic,
  type LocalFetchDiagnostic,
  type LocalTransportProbeDiagnostic,
  type PlatformFetch,
} from "./platform";
import { COMPUTE_PROTOCOL_VERSION, type ComputeClientStatus, type ComputeDevice, type ComputeOperation, type JsonObject, type LocalAnswerRequest, type LocalAnswerResponse, type LocalBootstrapResponse, type LocalComputeDocument, type LocalQueryRequest, type LocalQueryResponse, type LocalSession, type LocalSessionSnapshot, type PlatformGrant } from "./types";

export interface BrowserComputeClientOptions {
  platform?: PlatformComputeApi;
  localFetch?: typeof fetch;
  origin?: string;
  clock?: () => number;
  nonceFactory?: () => string;
}

type RequestBody = Uint8Array | undefined;

const RECONNECT_WINDOW_MS = 15000;
const RECONNECT_INITIAL_DELAY_MS = 250;
const RECONNECT_MAX_DELAY_MS = 2000;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function isAdmitted(device: ComputeDevice, operation: ComputeOperation): boolean {
  if (operation === "retrieval") {
    return device.capabilities?.retrieval === "READY" || device.capabilities?.retrieval === "ADMITTED";
  }

  return true;
}

function localBaseUrl(device: ComputeDevice, operation: ComputeOperation): string {
  if (device.state === "REVOKED") throw new BrowserComputeError("DEVICE_REVOKED");
  if (device.state === "UPDATE_REQUIRED") throw new BrowserComputeError("UPDATE_REQUIRED");
  if (device.state === "BUSY") throw new BrowserComputeError("DEVICE_BUSY");
  if (device.state !== "READY") throw new BrowserComputeError("DEVICE_OFFLINE");

  if (device.protocol_version !== COMPUTE_PROTOCOL_VERSION || !device.runtime_version) {
    throw new BrowserComputeError("PROTOCOL_VERSION_UNSUPPORTED");
  }

  if (!device.endpoint_generation) {
    throw new BrowserComputeError("ENDPOINT_GENERATION_UNAVAILABLE");
  }

  if (
    !Number.isInteger(device.endpoint_port) ||
    !device.endpoint_port ||
    device.endpoint_port < 1 ||
    device.endpoint_port > 65535
  ) {
    throw new BrowserComputeError("LOOPBACK_ENDPOINT_UNAVAILABLE");
  }

  if (!isAdmitted(device, operation)) {
    throw new BrowserComputeError("CAPABILITY_UNAVAILABLE");
  }

  return `http://127.0.0.1:${device.endpoint_port}`;
}

function toSnapshot(session: LocalSession): LocalSessionSnapshot {
  return {
    deviceId: session.deviceId,
    endpointGeneration: session.endpointGeneration,
    endpointPort: session.endpointPort,
    baseUrl: session.baseUrl,
    expiresAt: session.expiresAt,
    allowedOperations: session.allowedOperations,
    protocolVersion: session.protocolVersion,
  };
}

function operationFromPath(path: string): ComputeOperation {
  if (path === "/v1/runtime" || path === "/v1/capabilities" || /^\/v1\/jobs\/[^/]+(?::cancel)?$/.test(path)) return "jobs";
  if (path === "/v1/queries") return "retrieval";
  if (path === "/v1/answers") return "answer";
  return "documents";
}

function localAskBody(payload: LocalQueryRequest | LocalAnswerRequest): Uint8Array {
  if (typeof payload.query_text !== "string" || !payload.query_text.trim()) {
    throw new BrowserComputeError("INVALID_REQUEST", "A non-empty query is required.");
  }

  if (Array.isArray(payload.document_ids) && payload.document_ids.length === 0) {
    throw new BrowserComputeError(
      "EMPTY_DOCUMENT_SCOPE",
      "Select at least one local document or use all local documents.",
    );
  }

  return serializeJsonOnce({
    ...payload,
    ...(Array.isArray(payload.document_ids) ? { document_ids: [...payload.document_ids] } : {}),
  });
}

function encodeFilenameHeader(filename: string): string {
  const normalized = filename.normalize("NFC");

  if (!normalized || /[\u0000\r\n]/.test(normalized)) {
    throw new BrowserComputeError("INVALID_REQUEST", "Invalid document filename.");
  }

  try {
    return encodeURIComponent(normalized);
  } catch {
    throw new BrowserComputeError("INVALID_REQUEST", "Document filename could not be encoded.");
  }
}

type LocalFetchFailure = {
  diagnostic: Omit<LocalFetchDiagnostic, "operation" | "host_type" | "method" | "endpoint_path" | "local_session_present" | "browser_nonce_present" | "abort_signal_fired" | "request_timeout_configured" | "frontend_state">;
  error: BrowserComputeError;
};

type AnswerHeaderValidity = AnswerRequestPreparationDiagnostic["header_validity"];

const answerHeaderNames = [
  "origin",
  "content-type",
  "x-zkd-local-session",
  "x-zkd-timestamp",
  "x-zkd-nonce",
  "x-zkd-mac",
  "x-zkd-protocol-version",
] as const;

function safeHeaderValue(value: string, expression: RegExp): boolean {
  if (!value || /[\r\n]/.test(value) || !expression.test(value)) return false;
  try {
    new Headers({ "X-ZKD-Diagnostic": value });
    return true;
  } catch {
    return false;
  }
}

function answerHeaderValidity(
  headers: Record<string, string>,
  origin: string,
): AnswerHeaderValidity {
  const values = Object.fromEntries(
    Object.entries(headers).map(([name, value]) => [name.toLowerCase(), value]),
  ) as Record<string, string>;
  return {
    origin: values.origin === origin && safeHeaderValue(values.origin ?? "", /^https?:\/\/[^\s/]+/),
    "content-type": values["content-type"] === "application/json" && safeHeaderValue(values["content-type"] ?? "", /^application\/json$/),
    "x-zkd-local-session": safeHeaderValue(values["x-zkd-local-session"] ?? "", /^[0-9a-f]{8}-[0-9a-f-]{27}$/i),
    "x-zkd-timestamp": safeHeaderValue(values["x-zkd-timestamp"] ?? "", /^\d{10,13}$/),
    "x-zkd-nonce": safeHeaderValue(values["x-zkd-nonce"] ?? "", /^[A-Za-z0-9_-]{16,128}$/),
    "x-zkd-mac": safeHeaderValue(values["x-zkd-mac"] ?? "", /^[0-9a-f]{64}$/i),
    "x-zkd-protocol-version": values["x-zkd-protocol-version"] === COMPUTE_PROTOCOL_VERSION && safeHeaderValue(values["x-zkd-protocol-version"] ?? "", /^zkd-compute-v1$/),
  };
}

function answerRequestPreparation(
  url: string,
  init: RequestInit,
  headers: Record<string, string>,
  origin: string,
): AnswerRequestPreparationDiagnostic {
  const body = init.body;
  let bodyType: AnswerRequestPreparationDiagnostic["body_type"] = "OTHER";
  let byteLength = 0;
  let detached = false;

  if (body === undefined) {
    bodyType = "NONE";
  } else if (body instanceof ArrayBuffer) {
    bodyType = "ArrayBuffer";
    try {
      byteLength = body.byteLength;
      new Uint8Array(body);
    } catch {
      detached = true;
    }
  }

  const base = {
    operation: "answer_request_preparation" as const,
    body_type: bodyType,
    body_byte_length: byteLength,
    body_detached: detached,
    header_validity: answerHeaderValidity(headers, origin),
  };

  try {
    new Request(url, init);
    return {
      ...base,
      request_construction: "SUCCEEDED",
      exception_name: "None",
      classification: "REQUEST_CONSTRUCTION_SUCCEEDED",
    };
  } catch (error) {
    return {
      ...base,
      request_construction: "FAILED",
      exception_name: browserExceptionName(error),
      classification: "REQUEST_CONSTRUCTION_FAILED",
    };
  }
}

function browserExceptionName(error: unknown): LocalFetchDiagnostic["exception_name"] {
  const name = error && typeof error === "object" && "name" in error && typeof error.name === "string"
    ? error.name
    : "UnknownError";
  return ["TypeError", "AbortError", "NetworkError", "NotAllowedError"].includes(name)
    ? name as LocalFetchDiagnostic["exception_name"]
    : "UnknownError";
}

/** Classifies native fetch rejection without retaining or transmitting its raw text. */
function mapLocalFetchFailure(error: unknown): LocalFetchFailure {
  const exceptionName = browserExceptionName(error);
  const rawMessage = error instanceof Error ? error.message : "";

  if (exceptionName === "AbortError") {
    return {
      diagnostic: { phase: "abort", exception_name: exceptionName, exception_message: "LOCAL_FETCH_ABORTED", classification: "FETCH_ABORTED" },
      error: new BrowserComputeError("FETCH_ABORTED", "Local transport diagnostic: AbortError / LOCAL_FETCH_ABORTED. The browser aborted the local Compute request before it reached the service."),
    };
  }

  if (exceptionName === "NotAllowedError") {
    return {
      diagnostic: { phase: "actual-fetch", exception_name: exceptionName, exception_message: "LOCAL_FETCH_NOT_ALLOWED", classification: "ORIGIN_POLICY_REJECTED" },
      error: new BrowserComputeError("ORIGIN_POLICY_REJECTED", "Local transport diagnostic: NotAllowedError / LOCAL_FETCH_NOT_ALLOWED. The browser rejected the local Compute request under its origin policy."),
    };
  }

  if (exceptionName === "TypeError" && /headers|iso-8859-1|code point|body/i.test(rawMessage)) {
    return {
      diagnostic: { phase: "actual-fetch", exception_name: exceptionName, exception_message: "LOCAL_FETCH_BODY_OR_HEADER_REJECTED", classification: "BODY_INIT_INVALID" },
      error: new BrowserComputeError("INVALID_REQUEST", "Local transport diagnostic: TypeError / LOCAL_FETCH_BODY_OR_HEADER_REJECTED. Browser rejected the local request body or header before it could be sent."),
    };
  }

  if (exceptionName === "TypeError" || exceptionName === "NetworkError") {
    return {
      diagnostic: { phase: "actual-fetch", exception_name: exceptionName, exception_message: "LOCAL_FETCH_NETWORK_REJECTED", classification: "BROWSER_NETWORK_REJECTED" },
      error: new BrowserComputeError("BROWSER_NETWORK_REJECTED", `Local transport diagnostic: ${exceptionName} / LOCAL_FETCH_NETWORK_REJECTED. The browser rejected the local Compute network request before a response was received.`),
    };
  }

  return {
    diagnostic: { phase: "actual-fetch", exception_name: exceptionName, exception_message: "LOCAL_FETCH_OTHER_REJECTION", classification: "OTHER_BROWSER_FETCH_FAILURE" },
    error: new BrowserComputeError("OTHER_BROWSER_FETCH_FAILURE", `Local transport diagnostic: ${exceptionName} / LOCAL_FETCH_OTHER_REJECTION. The browser rejected the local Compute request before a response was received.`),
  };
}

async function parseLocalResponse<T>(response: Response): Promise<T> {
  let payload: unknown;

  try {
    payload = await response.json();
  } catch {
    payload = undefined;
  }

  if (!response.ok) {
    const source = payload as {
      error?: {
        code?: string;
        message?: string;
      };
      request_id?: string;
    } | undefined;

    const remoteCode = source?.error?.code;

    if (remoteCode === "CLOCK_SKEW") {
      throw new BrowserComputeError(
        "CLOCK_SKEW",
        source?.error?.message,
        response.status,
        source?.request_id,
      );
    }

    if (isSessionInvalidatingCode(remoteCode)) {
      throw new BrowserComputeError(
        remoteCode === "SESSION_EXPIRED" ? "SESSION_EXPIRED" : "SESSION_INVALID",
        source?.error?.message,
        response.status,
        source?.request_id,
      );
    }

    if (remoteCode === "UPDATE_REQUIRED") {
      throw new BrowserComputeError(
        "UPDATE_REQUIRED",
        source?.error?.message,
        response.status,
        source?.request_id,
      );
    }

    if (remoteCode === "NOT_PAIRED" || remoteCode === "DEVICE_REVOKED") {
      throw new BrowserComputeError(
        "NOT_PAIRED",
        source?.error?.message,
        response.status,
        source?.request_id,
      );
    }

    if (remoteCode === "OPERATION_NOT_ALLOWED") {
      throw new BrowserComputeError(
        "OPERATION_NOT_ALLOWED",
        source?.error?.message,
        response.status,
        source?.request_id,
      );
    }

    throw new BrowserComputeError(
      "REQUEST_FAILED",
      source?.error?.message ?? `Local request failed (${response.status})`,
      response.status,
      source?.request_id,
    );
  }

  if (payload === undefined) {
    throw new BrowserComputeError(
      "INVALID_LOCAL_RESPONSE",
      "Expected a JSON local response.",
      response.status,
    );
  }

  return payload as T;
}

export class BrowserComputeClient {
  private readonly platform: PlatformComputeApi;
  private readonly localFetch: typeof fetch;
  private readonly origin: string;
  private readonly clock: () => number;
  private readonly nonceFactory: () => string;

  private devices = new Map<string, ComputeDevice>();
  private selectedDeviceId: string | null = null;
  private session: LocalSession | null = null;
  private bootstrapInFlight: Promise<LocalSession> | null = null;
  private reconnectInFlight: Promise<boolean> | null = null;

  private async reportAnswerFetchFailure(failure: LocalFetchFailure): Promise<void> {
    // Diagnostics are intentionally best-effort and never alter the local request result.
    try {
      await this.platform.reportLocalFetchDiagnostic({
        operation: "answers",
        ...failure.diagnostic,
        host_type: "loopback",
        method: "POST",
        endpoint_path: "/v1/answers",
        local_session_present: true,
        browser_nonce_present: false,
        abort_signal_fired: false,
        request_timeout_configured: false,
        frontend_state: "AUTHENTICATED_REQUEST",
      });
    } catch {
      // Never convert a local transport failure into a platform diagnostic failure.
    }
  }

  private async reportAnswerRequestPreparation(
    diagnostic: AnswerRequestPreparationDiagnostic,
  ): Promise<void> {
    try {
      await this.platform.reportAnswerRequestPreparation(diagnostic);
    } catch {
      // Diagnostics must never change the answer request's transport result.
    }
  }

  private async reportTransportProbe(
    diagnostic: LocalTransportProbeDiagnostic,
  ): Promise<void> {
    try {
      await this.platform.reportLocalTransportProbeDiagnostic(diagnostic);
    } catch {
      // A platform diagnostic outage must not hide the local probe result.
    }
  }

  private async runAnswerTransportProbes(): Promise<void> {
    const probes: Array<{
      id: LocalTransportProbeDiagnostic["probe_id"];
      rawBody: Uint8Array;
      body: BodyInit | undefined;
      headers: Record<string, string>;
    }> = [
      { id: "P1", rawBody: new Uint8Array(), body: undefined, headers: {} },
      {
        id: "P2",
        rawBody: serializeJsonOnce({ probe: "p2" }),
        body: '{"probe":"p2"}',
        headers: { "Content-Type": "application/json" },
      },
      {
        id: "P3",
        rawBody: serializeJsonOnce({ probe: "p3" }),
        body: exactArrayBuffer(serializeJsonOnce({ probe: "p3" })),
        headers: { "Content-Type": "application/json" },
      },
    ];

    for (const probe of probes) {
      try {
        const session = await this.ensureSession("answer");
        const timestamp = String(Math.floor(this.clock()));
        const nonce = this.nonceFactory();
        const mac = await hmacSha256Hex(
          session.sessionKey,
          canonicalTranscript(
            "POST",
            "/v1/transport-probe",
            timestamp,
            nonce,
            await sha256Hex(probe.rawBody),
          ),
        );
        const response = await this.localFetch(
          `${session.baseUrl}/v1/transport-probe`,
          {
            method: "POST",
            headers: {
              Origin: this.origin,
              "X-ZKD-Local-Session": session.sessionId,
              "X-ZKD-Timestamp": timestamp,
              "X-ZKD-Nonce": nonce,
              "X-ZKD-MAC": mac,
              "X-ZKD-Protocol-Version": session.protocolVersion,
              ...probe.headers,
            },
            body: probe.body,
          },
        );
        await parseLocalResponse<{ status: string }>(response);
        await this.reportTransportProbe({
          operation: "transport_probe",
          probe_id: probe.id,
          success: true,
          exception_name: "None",
          classification: "PROBE_SUCCEEDED",
        });
      } catch (error) {
        const failure = mapLocalFetchFailure(error);
        await this.reportTransportProbe({
          operation: "transport_probe",
          probe_id: probe.id,
          success: false,
          exception_name: failure.diagnostic.exception_name,
          classification: failure.diagnostic.classification,
        });
      }
    }
  }

  constructor(options: BrowserComputeClientOptions = {}) {
    if (options.origin && options.origin !== window.location.origin) {
      throw new BrowserComputeError(
        "AUTH_FAILED",
        "Compute requests must use the browser application origin.",
      );
    }

    this.origin = window.location.origin;

    const browserFetch: typeof fetch = (input, init) => window.fetch(input, init);

    this.platform = options.platform ?? new PlatformComputeApi(browserFetch as PlatformFetch);
    this.localFetch = options.localFetch ?? browserFetch;
    this.clock = options.clock ?? (() => Date.now() / 1000);
    this.nonceFactory = options.nonceFactory ?? createBrowserNonce;
  }

  status(): ComputeClientStatus {
    return {
      selectedDeviceId: this.selectedDeviceId,
      session: this.session ? toSnapshot(this.session) : null,
    };
  }

  clearSession(): void {
    this.session = null;
  }

  logout(): void {
    this.session = null;
    this.selectedDeviceId = null;
    this.devices.clear();
  }

  disconnect(): void {
    this.clearSession();
  }

  async connect(
    operation: ComputeOperation = "jobs",
    deviceId?: string,
  ): Promise<LocalSessionSnapshot> {
    await this.selectDevice(operation, deviceId);
    return toSnapshot(await this.ensureSession(operation, deviceId));
  }

  async discover(): Promise<ComputeDevice[]> {
    const discovered = await this.platform.listDevices();

    this.devices = new Map(
      discovered.map((device) => [device.device_id, device]),
    );

    if (this.session) {
      const current = this.devices.get(this.session.deviceId);

      const endpointChanged =
        !current ||
        current.endpoint_generation !== this.session.endpointGeneration ||
        current.endpoint_port !== this.session.endpointPort;

      const deviceUnavailable =
        !current ||
        current.state !== "READY";

      const protocolChanged =
        Boolean(
          current &&
          current.protocol_version !== this.session.protocolVersion,
        );

      if (
        endpointChanged ||
        deviceUnavailable ||
        protocolChanged
      ) {
        this.clearSession();
      }
    }

    if (
      this.selectedDeviceId &&
      !this.devices.has(this.selectedDeviceId)
    ) {
      this.selectedDeviceId = null;
    }

    return discovered;
  }

  async localManifests() {
    return this.platform.listLocalManifests();
  }

  async selectDevice(
    operation: ComputeOperation,
    deviceId?: string,
  ): Promise<ComputeDevice> {
    if (!this.devices.size) {
      await this.discover();
    }

    if (deviceId) {
      const requested = this.devices.get(deviceId);

      if (!requested) {
        throw new BrowserComputeError(
          "NO_DEVICE",
          "Selected compute device was not found.",
        );
      }

      localBaseUrl(requested, operation);

      if (
        this.selectedDeviceId &&
        this.selectedDeviceId !== requested.device_id
      ) {
        this.clearSession();
      }

      this.selectedDeviceId = requested.device_id;
      return requested;
    }

    if (this.selectedDeviceId) {
      const selected = this.devices.get(this.selectedDeviceId);

      if (selected) {
        localBaseUrl(selected, operation);
        return selected;
      }
    }

    const available = Array.from(this.devices.values()).filter((candidate) => {
      try {
        localBaseUrl(candidate, operation);
        return true;
      } catch {
        return false;
      }
    });

    if (!available.length) {
      if (
        Array.from(this.devices.values()).some(
          (device) => device.state === "REVOKED",
        )
      ) {
        throw new BrowserComputeError("DEVICE_REVOKED");
      }

      throw new BrowserComputeError(
        this.devices.size ? "DEVICE_OFFLINE" : "NO_DEVICE",
      );
    }

    if (available.length > 1) {
      throw new BrowserComputeError("DEVICE_SELECTION_REQUIRED");
    }

    this.selectedDeviceId = available[0].device_id;
    return available[0];
  }

  private sessionIsUsable(operation: ComputeOperation): boolean {
    return Boolean(
      this.session &&
      this.session.expiresAt > Math.floor(this.clock()) &&
      this.session.allowedOperations.includes(operation),
    );
  }

  async ensureSession(
    operation: ComputeOperation,
    deviceId?: string,
  ): Promise<LocalSession> {
    if (
      this.sessionIsUsable(operation) &&
      (!deviceId || this.session?.deviceId === deviceId)
    ) {
      return this.session as LocalSession;
    }

    if (
      this.session &&
      this.session.expiresAt <= Math.floor(this.clock())
    ) {
      this.clearSession();
    }

    if (
      this.session &&
      (!deviceId || this.session.deviceId === deviceId) &&
      !this.session.allowedOperations.includes(operation)
    ) {
      throw new BrowserComputeError("OPERATION_NOT_ALLOWED");
    }

    if (this.bootstrapInFlight) {
      return this.bootstrapInFlight;
    }

    this.bootstrapInFlight = this.bootstrap(
      operation,
      deviceId,
    ).finally(() => {
      this.bootstrapInFlight = null;
    });

    return this.bootstrapInFlight;
  }

  private async bootstrap(
    operation: ComputeOperation,
    deviceId?: string,
  ): Promise<LocalSession> {
    const device = await this.selectDevice(operation, deviceId);
    const baseUrl = localBaseUrl(device, operation);
    const browserNonce = this.nonceFactory();

    let grant: PlatformGrant;

    try {
      grant = await this.platform.requestLocalSessionGrant(
        device.device_id,
        browserNonce,
      );
    } catch (error) {
      throw error instanceof BrowserComputeError
        ? error
        : new BrowserComputeError("PLATFORM_UNAVAILABLE");
    }

    if (
      grant.device_id !== device.device_id ||
      grant.endpoint_generation !== device.endpoint_generation
    ) {
      this.clearSession();

      throw new BrowserComputeError(
        "SESSION_INVALID",
        "Platform grant does not match the selected device endpoint.",
      );
    }

    let response: Response;

    try {
      response = await this.localFetch(
        `${baseUrl}/v1/sessions`,
        {
          method: "POST",
          headers: {
            Origin: this.origin,
            "X-ZKD-Local-Grant": grant.local_access_grant,
            "X-ZKD-Browser-Nonce": browserNonce,
          },
        },
      );
    } catch (error) {
      throw mapLocalFetchFailure(error);
    }

    const bootstrapped =
      await parseLocalResponse<LocalBootstrapResponse>(response);

    if (
      bootstrapped.protocol_version !== COMPUTE_PROTOCOL_VERSION ||
      bootstrapped.endpoint_generation !== device.endpoint_generation
    ) {
      this.clearSession();

      throw new BrowserComputeError(
        "SESSION_INVALID",
        "Local session response does not match the selected endpoint.",
      );
    }

    const allowed = bootstrapped.allowed_operations.filter(
      (value): value is ComputeOperation =>
        ["documents", "jobs", "retrieval", "answer"].includes(value),
    );

    if (!allowed.includes(operation)) {
      throw new BrowserComputeError("OPERATION_NOT_ALLOWED");
    }

    const session: LocalSession = {
      deviceId: device.device_id,
      endpointGeneration: device.endpoint_generation!,
      endpointPort: device.endpoint_port!,
      baseUrl,
      sessionId: bootstrapped.local_session_id,
      sessionKey: bootstrapped.session_key,
      expiresAt: bootstrapped.expires_at,
      allowedOperations: allowed,
      protocolVersion: bootstrapped.protocol_version,
    };

    this.session = session;
    return session;
  }

  private async reconnectAfterTransportFailure(
    operation: ComputeOperation,
    failedSession: LocalSession,
  ): Promise<boolean> {
    if (this.reconnectInFlight) {
      return this.reconnectInFlight;
    }

    this.reconnectInFlight = this.performReconnect(
      operation,
      failedSession,
    ).finally(() => {
      this.reconnectInFlight = null;
    });

    return this.reconnectInFlight;
  }

  private async performReconnect(
    operation: ComputeOperation,
    failedSession: LocalSession,
  ): Promise<boolean> {
    const deadline = Date.now() + RECONNECT_WINDOW_MS;
    let delayMs = RECONNECT_INITIAL_DELAY_MS;

    this.clearSession();

    while (Date.now() < deadline) {
      try {
        await this.discover();

        const current = this.devices.get(failedSession.deviceId);

        if (current) {
          try {
            localBaseUrl(current, operation);

            this.selectedDeviceId = current.device_id;
            this.clearSession();

            await this.ensureSession(
              operation,
              current.device_id,
            );

            return true;
          } catch (error) {
            if (
              error instanceof BrowserComputeError &&
              (
                error.code === "DEVICE_REVOKED" ||
                error.code === "UPDATE_REQUIRED" ||
                error.code === "PROTOCOL_VERSION_UNSUPPORTED"
              )
            ) {
              throw error;
            }
          }
        }
      } catch (error) {
        if (
          error instanceof BrowserComputeError &&
          (
            error.code === "DEVICE_REVOKED" ||
            error.code === "UPDATE_REQUIRED" ||
            error.code === "PROTOCOL_VERSION_UNSUPPORTED"
          )
        ) {
          throw error;
        }
      }

      const remaining = deadline - Date.now();

      if (remaining <= 0) {
        break;
      }

      await sleep(
        Math.min(
          delayMs,
          remaining,
        ),
      );

      delayMs = Math.min(
        delayMs * 2,
        RECONNECT_MAX_DELAY_MS,
      );
    }

    return false;
  }

  private async localRequest<T>(
    method: string,
    path: string,
    body: RequestBody,
    headers: Record<string, string> = {},
  ): Promise<T> {
    const operation = operationFromPath(path);
    const rawBody = body ?? new Uint8Array();

    for (let attempt = 0; attempt < 2; attempt += 1) {
      const session = await this.ensureSession(operation);

      if (!this.sessionIsUsable(operation)) {
        this.clearSession();
        throw new BrowserComputeError("SESSION_EXPIRED");
      }

      const timestamp = String(Math.floor(this.clock()));
      const nonce = this.nonceFactory();

      let mac: string;

      try {
        mac = await hmacSha256Hex(
          session.sessionKey,
          canonicalTranscript(
            method,
            path,
            timestamp,
            nonce,
            await sha256Hex(rawBody),
          ),
        );
      } catch (error) {
        if ((error as Error).message === "INVALID_REQUEST_PATH") {
          throw new BrowserComputeError("INVALID_REQUEST_PATH");
        }

        throw error;
      }

      let response: Response;

      try {
        const requestHeaders = {
          Origin: this.origin,
          "X-ZKD-Local-Session": session.sessionId,
          "X-ZKD-Timestamp": timestamp,
          "X-ZKD-Nonce": nonce,
          "X-ZKD-MAC": mac,
          "X-ZKD-Protocol-Version": session.protocolVersion,
          ...headers,
        };
        const requestInit: RequestInit = {
          method,
          headers: requestHeaders,
          body: rawBody.length
            ? exactArrayBuffer(rawBody)
            : undefined,
        };

        if (path === "/v1/answers" && method === "POST") {
          const preparation = answerRequestPreparation(
            `${session.baseUrl}${path}`,
            requestInit,
            requestHeaders,
            this.origin,
          );
          await this.reportAnswerRequestPreparation(preparation);
          if (preparation.request_construction === "FAILED") {
            throw new BrowserComputeError(
              "INVALID_REQUEST",
              "Local transport diagnostic: request construction failed before the browser could send the answer request.",
            );
          }
        }

        response = await this.localFetch(
          `${session.baseUrl}${path}`,
          requestInit,
        );
      } catch (error) {
        const failure = mapLocalFetchFailure(error);

        if (path === "/v1/answers" && method === "POST") {
          await this.reportAnswerFetchFailure(failure);
          await this.runAnswerTransportProbes();
        }

        if (
          attempt === 0 &&
          failure.error.code === "LOCAL_COMPUTE_UNAVAILABLE"
        ) {
          const recovered =
            await this.reconnectAfterTransportFailure(
              operation,
              session,
            );

          if (recovered) {
            continue;
          }
        }

        throw failure.error;
      }

      try {
        return await parseLocalResponse<T>(response);
      } catch (error) {
        if (
          error instanceof BrowserComputeError &&
          (
            isSessionInvalidatingCode(error.code) ||
            isDeviceInvalidatingCode(error.code)
          )
        ) {
          this.clearSession();
        }

        throw error;
      }
    }

    throw new BrowserComputeError("LOCAL_COMPUTE_UNAVAILABLE");
  }

  async runtime() {
    return this.localRequest<JsonObject>(
      "GET",
      "/v1/runtime",
      undefined,
    );
  }

  async capabilities() {
    return this.localRequest<JsonObject>(
      "GET",
      "/v1/capabilities",
      undefined,
    );
  }

  async uploadSource(
    documentId: string,
    file: Blob | ArrayBuffer | Uint8Array,
    filename: string,
  ) {
    return this.localRequest<JsonObject>(
      "PUT",
      `/v1/documents/${encodeURIComponent(documentId)}/source`,
      await binaryBodyBytes(file),
      {
        "Content-Type": "application/pdf",
        "X-ZKD-Filename": encodeFilenameHeader(filename),
      },
    );
  }

  async listDocuments(): Promise<LocalComputeDocument[]> {
    return (
      await this.localRequest<{
        documents: LocalComputeDocument[];
      }>(
        "GET",
        "/v1/documents",
        undefined,
      )
    ).documents;
  }

  async prepareDocument(documentId: string) {
    return this.localRequest<JsonObject>(
      "POST",
      `/v1/documents/${encodeURIComponent(documentId)}/prepare`,
      undefined,
    );
  }

  async documentState(documentId: string) {
    return this.localRequest<JsonObject>(
      "GET",
      `/v1/documents/${encodeURIComponent(documentId)}`,
      undefined,
    );
  }

  async deleteDocument(documentId: string) {
    return this.localRequest<JsonObject>(
      "DELETE",
      `/v1/documents/${encodeURIComponent(documentId)}`,
      undefined,
    );
  }

  async indexDocument(documentId: string) {
    return this.localRequest<JsonObject>(
      "POST",
      `/v1/documents/${encodeURIComponent(documentId)}/index`,
      undefined,
    );
  }

  async jobState(jobId: string) {
    return this.localRequest<JsonObject>(
      "GET",
      `/v1/jobs/${encodeURIComponent(jobId)}`,
      undefined,
    );
  }

  async cancelJob(jobId: string) {
    return this.localRequest<JsonObject>(
      "POST",
      `/v1/jobs/${encodeURIComponent(jobId)}:cancel`,
      undefined,
    );
  }

  async query(
    payload: LocalQueryRequest,
  ): Promise<LocalQueryResponse> {
    return this.localRequest<LocalQueryResponse>(
      "POST",
      "/v1/queries",
      localAskBody(payload),
      {
        "Content-Type": "application/json",
      },
    );
  }

  async answer(
    payload: LocalAnswerRequest,
  ): Promise<LocalAnswerResponse> {
    return this.localRequest<LocalAnswerResponse>(
      "POST",
      "/v1/answers",
      localAskBody(payload),
      {
        "Content-Type": "application/json",
      },
    );
  }
}
