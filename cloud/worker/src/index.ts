import passwordPolicy from "../../password_policy.json";

/**
 * ZKD's Cloudflare-resident metadata control plane.
 *
 * This Worker intentionally has no routes or columns for PDFs, document text,
 * chunks, embeddings, retrieval context, prompts, or generated answers.
 */
export interface Env {
  DB: D1Database;
  ASSETS: Fetcher;
  PUBLIC_ORIGIN: string;
  SESSION_TTL_SECONDS: string;
  PRESENCE_TTL_SECONDS: string;
  GRANT_SIGNING_PRIVATE_KEY_B64: string;
  GOOGLE_CLIENT_ID?: string;
  GOOGLE_CLIENT_SECRET?: string;
}

type User = { id: string; email: string; role: string; status: string };
type Device = {
  id: string; owner_user_id: string; public_key_b64: string; friendly_label: string | null;
  credential_epoch: number; protocol_version: string; runtime_version: string; revoked_at: number | null;
};
const protocolVersion = "zkd-compute-v1";
const capabilities = new Set(["pdf_processing", "chunking", "embedding", "indexing", "retrieval", "generation"]);
const states = new Set(["OFFLINE", "CONNECTING", "AUTHENTICATING", "READY", "BUSY", "DEGRADED", "UNAVAILABLE", "UPDATE_REQUIRED"]);
const forbidden = new Set(["pdf_bytes", "page_text", "reconstructed_text", "chunk_text", "chunks", "embedding", "embeddings", "vector", "prompt", "context", "answer", "query", "credential", "secret", "private_key"]);
const grantOperations = ["documents", "jobs", "retrieval", "answer"];
const localFetchDiagnosticFields = new Set([
  "operation", "phase", "exception_name", "exception_message", "host_type",
  "method", "endpoint_path", "local_session_present", "browser_nonce_present",
  "abort_signal_fired", "request_timeout_configured", "frontend_state", "classification",
]);
const localTransportProbeDiagnosticFields = new Set([
  "operation", "probe_id", "success", "exception_name", "classification",
]);
const answerRequestPreparationDiagnosticFields = new Set([
  "operation", "body_type", "body_byte_length", "body_detached",
  "request_construction", "exception_name", "classification", "header_validity",
]);
const localFetchDiagnosticValues = {
  operation: new Set(["answers"]),
  phase: new Set(["actual-fetch", "abort"]),
  exception_name: new Set(["TypeError", "AbortError", "NetworkError", "NotAllowedError", "UnknownError"]),
  exception_message: new Set(["LOCAL_FETCH_ABORTED", "LOCAL_FETCH_BODY_OR_HEADER_REJECTED", "LOCAL_FETCH_NETWORK_REJECTED", "LOCAL_FETCH_NOT_ALLOWED", "LOCAL_FETCH_OTHER_REJECTION"]),
  host_type: new Set(["loopback"]),
  method: new Set(["POST"]),
  endpoint_path: new Set(["/v1/answers"]),
  frontend_state: new Set(["AUTHENTICATED_REQUEST"]),
  classification: new Set(["FETCH_ABORTED", "BODY_INIT_INVALID", "BROWSER_NETWORK_REJECTED", "ORIGIN_POLICY_REJECTED", "OTHER_BROWSER_FETCH_FAILURE"]),
};
const encoder = new TextEncoder();
let jwksCache: { keys: JsonWebKey[]; expiresAt: number } | undefined;

class ApiError extends Error {
  constructor(readonly code: string, readonly status: number) {
    super(code);
  }
}

const json = (body: unknown, status = 200, headers: HeadersInit = {}) => new Response(JSON.stringify(body), {
  status, headers: { "content-type": "application/json", "cache-control": "no-store", ...headers },
});
const error = (code: string, status: number, message?: string) => json({ detail: { error_code: code, message: message ?? code.replaceAll("_", " ") } }, status);
const bytes = (value: string) => encoder.encode(value);
const nowMs = () => Date.now();
const unix = () => Math.floor(nowMs() / 1000);
const b64 = (value: Uint8Array) => { let result = ""; for (const byte of value) result += String.fromCharCode(byte); return btoa(result); };
const b64url = (value: Uint8Array) => b64(value).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
const b64decode = (value: string) => Uint8Array.from(atob(value.replaceAll("-", "+").replaceAll("_", "/") + "=".repeat((4 - value.length % 4) % 4)), char => char.charCodeAt(0));
const ed25519Pkcs8Prefix = Uint8Array.from([
  // PrivateKeyInfo(version=0, algorithm=id-Ed25519, privateKey=CurvePrivateKey).
  // RFC 8410: 30 2e 02 01 00 30 05 06 03 2b 65 70 04 22 04 20 || seed.
  0x30, 0x2e, 0x02, 0x01, 0x00, 0x30, 0x05, 0x06,
  0x03, 0x2b, 0x65, 0x70, 0x04, 0x22, 0x04, 0x20,
]);
const canonicalBase64 = /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/;
async function sha(value: string | Uint8Array) { return b64url(new Uint8Array(await crypto.subtle.digest("SHA-256", typeof value === "string" ? bytes(value) : value))); }
async function shaHex(value: Uint8Array) { return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", value)), byte => byte.toString(16).padStart(2, "0")).join(""); }
function isObject(value: unknown): value is Record<string, unknown> { return !!value && typeof value === "object" && !Array.isArray(value); }
function hasForbidden(value: unknown) { return isObject(value) && Object.keys(value).some(key => forbidden.has(key)); }
function hasExactFields(value: Record<string, unknown>, fields: Set<string>) {
  return Object.keys(value).length === fields.size && Object.keys(value).every(key => fields.has(key));
}
function validAnswerFetchDiagnostic(value: unknown) {
  if (!isObject(value) || !hasExactFields(value, localFetchDiagnosticFields)) return false;
  const bools = ["local_session_present", "browser_nonce_present", "abort_signal_fired", "request_timeout_configured"];
  if (bools.some(key => typeof value[key] !== "boolean")) return false;
  return Object.entries(localFetchDiagnosticValues).every(([key, values]) => typeof value[key] === "string" && values.has(value[key]));
}
function validTransportProbeDiagnostic(value: unknown) {
  if (!isObject(value) || !hasExactFields(value, localTransportProbeDiagnosticFields)) return false;
  return value.operation === "transport_probe"
    && ["P1", "P2", "P3"].includes(String(value.probe_id))
    && typeof value.success === "boolean"
    && ["None", "TypeError", "AbortError", "NetworkError", "NotAllowedError", "UnknownError"].includes(String(value.exception_name))
    && ["PROBE_SUCCEEDED", "FETCH_ABORTED", "BODY_INIT_INVALID", "BROWSER_NETWORK_REJECTED", "ORIGIN_POLICY_REJECTED", "OTHER_BROWSER_FETCH_FAILURE"].includes(String(value.classification));
}
function validAnswerRequestPreparationDiagnostic(value: unknown) {
  if (!isObject(value) || !hasExactFields(value, answerRequestPreparationDiagnosticFields)) return false;
  const headerNames = ["origin", "content-type", "x-zkd-local-session", "x-zkd-timestamp", "x-zkd-nonce", "x-zkd-mac", "x-zkd-protocol-version"];
  const headerValidity = value.header_validity;
  return value.operation === "answer_request_preparation"
    && ["ArrayBuffer", "NONE", "OTHER"].includes(String(value.body_type))
    && Number.isInteger(value.body_byte_length) && Number(value.body_byte_length) >= 0 && Number(value.body_byte_length) <= 1048576
    && typeof value.body_detached === "boolean"
    && ["SUCCEEDED", "FAILED"].includes(String(value.request_construction))
    && ["None", "TypeError", "AbortError", "NetworkError", "NotAllowedError", "UnknownError"].includes(String(value.exception_name))
    && ["REQUEST_CONSTRUCTION_SUCCEEDED", "REQUEST_CONSTRUCTION_FAILED"].includes(String(value.classification))
    && isObject(headerValidity) && headerNames.length === Object.keys(headerValidity).length
    && headerNames.every(name => typeof headerValidity[name] === "boolean");
}
function validLocalFetchDiagnostic(value: unknown) {
  return validAnswerFetchDiagnostic(value)
    || validTransportProbeDiagnostic(value)
    || validAnswerRequestPreparationDiagnostic(value);
}
function cookie(request: Request, name: string) { return request.headers.get("cookie")?.split(";").map(value => value.trim()).find(value => value.startsWith(`${name}=`))?.slice(name.length + 1); }
function sameOrigin(request: Request, env: Env) { return request.headers.get("origin") === env.PUBLIC_ORIGIN; }
function requestPath(request: Request) { return new URL(request.url).pathname; }
function fixedTimeEqual(left: Uint8Array, right: Uint8Array) { if (left.length !== right.length) return false; let diff = 0; for (let index = 0; index < left.length; index++) diff |= left[index] ^ right[index]; return diff === 0; }
function redirect(location: string, headers: HeadersInit = {}) { return new Response(null, { status: 302, headers: { location, "cache-control": "no-store", ...headers } }); }
function redirectWithCookies(location: string, cookies: string[]) {
  const headers = new Headers({ location, "cache-control": "no-store" });
  for (const value of cookies) headers.append("set-cookie", value);
  return new Response(null, { status: 302, headers });
}
function oauthCookie(value: string, maxAge?: number) { return `zkd_google_tx=${value}; Path=/; HttpOnly; Secure; SameSite=Lax${maxAge === undefined ? "; Max-Age=0" : `; Max-Age=${maxAge}`}`; }
function random() { return b64url(crypto.getRandomValues(new Uint8Array(32))); }
async function pkceChallenge(verifier: string) { return b64url(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes(verifier)))); }
function callbackUrl(env: Env) { return `${env.PUBLIC_ORIGIN}/api/v1/auth/google/callback`; }
function oauthFailure(code: string) { console.warn("google_auth_failure", { code }); return redirect(`/?auth_error=${encodeURIComponent(code)}`, { "set-cookie": oauthCookie("") }); }
function decodeJson(value: string) { return JSON.parse(new TextDecoder().decode(b64decode(value))) as Record<string, unknown>; }
async function googleJwks(force = false) {
  if (!force && jwksCache && jwksCache.expiresAt > nowMs()) return jwksCache.keys;
  const response = await fetch("https://www.googleapis.com/oauth2/v3/certs");
  if (!response.ok) throw new Error("GOOGLE_JWKS_UNAVAILABLE");
  const payload = await response.json() as { keys?: JsonWebKey[] };
  if (!Array.isArray(payload.keys)) throw new Error("GOOGLE_JWKS_INVALID");
  jwksCache = { keys: payload.keys, expiresAt: nowMs() + 3600000 };
  return payload.keys;
}
async function verifyGoogleIdToken(idToken: string, env: Env, nonce: string) {
  const parts = idToken.split("."); if (parts.length !== 3) throw new Error("GOOGLE_ID_TOKEN_INVALID");
  const header = decodeJson(parts[0]); const claims = decodeJson(parts[1]);
  if (header.alg !== "RS256" || typeof header.kid !== "string") throw new Error("GOOGLE_ID_TOKEN_INVALID");
  let keys = await googleJwks(); let jwk = keys.find(key => key.kid === header.kid);
  if (!jwk) { keys = await googleJwks(true); jwk = keys.find(key => key.kid === header.kid); }
  if (!jwk) throw new Error("GOOGLE_ID_TOKEN_INVALID");
  const key = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
  if (!await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, b64decode(parts[2]), bytes(`${parts[0]}.${parts[1]}`))) throw new Error("GOOGLE_ID_TOKEN_INVALID");
  const now = unix(); const issuer = claims.iss; const audience = claims.aud;
  if ((issuer !== "https://accounts.google.com" && issuer !== "accounts.google.com") || audience !== env.GOOGLE_CLIENT_ID || typeof claims.exp !== "number" || claims.exp <= now || typeof claims.iat === "number" && claims.iat > now + 300 || claims.nonce !== nonce || typeof claims.sub !== "string" || !claims.sub || typeof claims.email !== "string" || claims.email_verified !== true) throw new Error("GOOGLE_ID_TOKEN_CLAIMS_INVALID");
  return { sub: claims.sub, email: claims.email.toLowerCase() };
}
async function createSession(env: Env, user: User) { const token = b64url(crypto.getRandomValues(new Uint8Array(32))); await env.DB.prepare("INSERT INTO sessions(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)").bind(await sha(token), user.id, nowMs() + Number(env.SESSION_TTL_SECONDS) * 1000, nowMs()).run(); return token; }
async function resolveGoogleIdentity(env: Env, sub: string, email: string): Promise<User> {
  const mapped = await env.DB.prepare("SELECT u.id,u.email,u.role,u.status FROM user_identities i JOIN users u ON u.id=i.user_id WHERE i.provider='google' AND i.provider_subject=?").bind(sub).first<User>();
  if (mapped) return mapped;
  const existing = await env.DB.prepare("SELECT id,email,role,status FROM users WHERE lower(email)=lower(?)").bind(email).first<User>();
  const user: User = existing ?? { id: crypto.randomUUID(), email, role: "USER", status: "ACTIVE" };
  try {
    const statements = existing ? [] : [env.DB.prepare("INSERT INTO users(id,email,password_hash,role,status,created_at) VALUES(?,?,NULL,'USER','ACTIVE',?)").bind(user.id, email, nowMs())];
    statements.push(env.DB.prepare("INSERT INTO user_identities(provider,provider_subject,user_id,email_at_link_time,created_at,updated_at) VALUES('google',?,?,?,?,?)").bind(sub, user.id, email, nowMs(), nowMs()));
    await env.DB.batch(statements);
  } catch { throw new Error("GOOGLE_ACCOUNT_LINK_CONFLICT"); }
  console.info(existing ? "google_identity_linked" : "google_account_created", { user_id: user.id }); return user;
}

async function getPrincipal(request: Request, env: Env): Promise<User | null> {
  const raw = cookie(request, "zkd_session");
  if (!raw) return null;
  const row = await env.DB.prepare("SELECT u.id,u.email,u.role,u.status FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?").bind(await sha(raw), nowMs()).first<User>();
  return row?.status === "ACTIVE" ? row : null;
}
async function inspectAuthMePrincipal(request: Request, env: Env) {
  const raw = cookie(request, "zkd_session");
  if (!raw) return { user: null, cookiePresent: false, sessionFound: false, userFound: false };
  const session = await env.DB.prepare("SELECT user_id FROM sessions WHERE token_hash=? AND expires_at>?").bind(await sha(raw), nowMs()).first<{ user_id: string }>();
  if (!session) return { user: null, cookiePresent: true, sessionFound: false, userFound: false };
  const user = await env.DB.prepare("SELECT id,email,role,status FROM users WHERE id=?").bind(session.user_id).first<User>();
  return { user: user?.status === "ACTIVE" ? user : null, cookiePresent: true, sessionFound: true, userFound: !!user };
}
async function requireUser(request: Request, env: Env) { const user = await getPrincipal(request, env); if (!user) throw new ApiError("AUTHENTICATION_REQUIRED", 401); return user; }
function cookieHeader(value: string, maxAge?: number) { return `zkd_session=${value}; Path=/; HttpOnly; Secure; SameSite=Lax${maxAge === undefined ? "; Max-Age=0" : `; Max-Age=${maxAge}`}`; }
async function parseJson(request: Request) { try { const value: unknown = await request.json(); return value; } catch { throw new ApiError("INVALID_JSON", 400); } }
async function loginRateKey(request: Request, email: string) { return sha(`${request.headers.get("cf-connecting-ip") ?? "unknown"}|${email.trim().toLowerCase()}`); }
async function allowLogin(request: Request, env: Env, email: string) {
  const key = await loginRateKey(request, email); const now = nowMs(); const windowMs = 15 * 60 * 1000;
  const row = await env.DB.prepare("SELECT window_started_at,attempts FROM login_rate_limits WHERE key_hash=?").bind(key).first<{ window_started_at: number; attempts: number }>();
  return { key, allowed: !row || row.window_started_at + windowMs <= now || row.attempts < 10 };
}
async function recordFailedLogin(env: Env, key: string) {
  const now = nowMs(); const windowMs = 15 * 60 * 1000;
  await env.DB.prepare("INSERT INTO login_rate_limits(key_hash,window_started_at,attempts) VALUES(?,?,1) ON CONFLICT(key_hash) DO UPDATE SET window_started_at=CASE WHEN login_rate_limits.window_started_at+?<=excluded.window_started_at THEN excluded.window_started_at ELSE login_rate_limits.window_started_at END,attempts=CASE WHEN login_rate_limits.window_started_at+?<=excluded.window_started_at THEN 1 ELSE login_rate_limits.attempts+1 END").bind(key, now, windowMs, windowMs).run();
}

/** D1 auth uses PBKDF2. Existing Argon2 credentials require the documented reset/migration process. */
async function verifyPassword(stored: string, password: string) {
  if (!stored) return false;
  const [scheme, iterationText, salt, expected] = stored.split("$");
  if (scheme !== passwordPolicy.scheme || !iterationText || !salt || !expected) return false;
  const iterations = Number(iterationText);
  if (!Number.isSafeInteger(iterations) || iterations !== passwordPolicy.iterations) {
    console.warn("AUTH_PASSWORD_SCHEME_UNSUPPORTED", { scheme, iterations });
    return false;
  }
  try {
    const expectedBytes = b64decode(expected);
    if (expectedBytes.length !== passwordPolicy.derived_key_bytes || b64decode(salt).length < passwordPolicy.salt_bytes) return false;
    const key = await crypto.subtle.importKey("raw", bytes(password), "PBKDF2", false, ["deriveBits"]);
    const actual = new Uint8Array(await crypto.subtle.deriveBits({ name: "PBKDF2", salt: b64decode(salt), iterations, hash: "SHA-256" }, key, expectedBytes.length * 8));
    return fixedTimeEqual(actual, expectedBytes);
  } catch {
    console.warn("AUTH_PASSWORD_RECORD_INVALID");
    return false;
  }
}

/**
 * The secret is a standard-base64 encoded raw 32-byte Ed25519 seed. WebCrypto
 * reserves "raw" Ed25519 for public keys, so signing material must be wrapped
 * as RFC 8410 PKCS#8 before import. The seed never leaves memory.
 */
function grantSigningSeed(secret: string) {
  if (typeof secret !== "string" || !canonicalBase64.test(secret)) throw new Error("GRANT_SIGNING_KEY_INVALID");
  let seed: Uint8Array;
  try { seed = b64decode(secret); } catch { throw new Error("GRANT_SIGNING_KEY_INVALID"); }
  if (seed.length !== 32) throw new Error("GRANT_SIGNING_KEY_INVALID");
  return seed;
}

function ed25519Pkcs8(seed: Uint8Array) {
  if (seed.length !== 32) throw new Error("GRANT_SIGNING_KEY_INVALID");
  const result = new Uint8Array(ed25519Pkcs8Prefix.length + seed.length);
  result.set(ed25519Pkcs8Prefix);
  result.set(seed, ed25519Pkcs8Prefix.length);
  return result;
}

export async function importGrantSigningPrivateKey(secret: string) {
  try {
    return await crypto.subtle.importKey("pkcs8", ed25519Pkcs8(grantSigningSeed(secret)), { name: "Ed25519" }, false, ["sign"]);
  } catch { throw new Error("GRANT_SIGNING_KEY_INVALID"); }
}

export async function signGrant(env: Env, claims: object) {
  const raw = b64url(bytes(JSON.stringify(claims)));
  const key = await importGrantSigningPrivateKey(env.GRANT_SIGNING_PRIVATE_KEY_B64);
  return `${raw}.${b64url(new Uint8Array(await crypto.subtle.sign("Ed25519", key, bytes(raw))))}`;
}
async function canonicalDeviceRequest(request: Request, epoch: number, timestamp: string, nonce: string, body: Uint8Array) {
  // This is byte-for-byte the frozen local `canonical_device_request` transcript.
  return bytes([request.method.toUpperCase(), requestPath(request), String(epoch), timestamp, nonce, await shaHex(body)].join("|"));
}
async function authenticateDevice(request: Request, env: Env, body: Uint8Array): Promise<Device> {
  const headers = request.headers;
  const id = headers.get("X-ZKD-Device-ID") ?? "";
  const epoch = Number(headers.get("X-ZKD-Credential-Epoch"));
  const timestamp = headers.get("X-ZKD-Timestamp") ?? "";
  const nonce = headers.get("X-ZKD-Nonce") ?? "";
  const signature = headers.get("X-ZKD-Signature") ?? "";
  if (!id || !Number.isInteger(epoch) || !timestamp || !nonce || !signature) throw new ApiError("DEVICE_AUTH_INVALID", 403);
  const device = await env.DB.prepare("SELECT * FROM devices WHERE id=?").bind(id).first<Device>();
  if (!device) throw new ApiError("DEVICE_NOT_FOUND", 404);
  if (device.revoked_at !== null) throw new ApiError("DEVICE_REVOKED", 403);
  if (device.credential_epoch !== epoch || Math.abs(unix() - Number(timestamp)) > 300) throw new ApiError("DEVICE_AUTH_INVALID", 403);
  try {
    const publicKey = await crypto.subtle.importKey("raw", b64decode(device.public_key_b64), { name: "Ed25519" }, false, ["verify"]);
    if (!await crypto.subtle.verify("Ed25519", publicKey, b64decode(signature), await canonicalDeviceRequest(request, epoch, timestamp, nonce, body))) throw new Error("invalid signature");
  } catch { throw new ApiError("DEVICE_AUTH_INVALID", 403); }
  const nonceHash = await sha(nonce);
  await env.DB.prepare("DELETE FROM replay_nonces WHERE expires_at<?").bind(nowMs()).run();
  const prior = await env.DB.prepare("SELECT 1 FROM replay_nonces WHERE device_id=? AND nonce_hash=?").bind(device.id, nonceHash).first();
  if (prior) throw new ApiError("DEVICE_REPLAY_DETECTED", 403);
  await env.DB.prepare("INSERT INTO replay_nonces(device_id,nonce_hash,expires_at) VALUES(?,?,?)").bind(device.id, nonceHash, nowMs() + 300000).run();
  return device;
}
async function deviceState(env: Env, device: Device) {
  const presence = await env.DB.prepare("SELECT * FROM device_presence WHERE device_id=?").bind(device.id).first<any>();
  const fresh = !!presence && presence.last_seen_at >= nowMs() - Number(env.PRESENCE_TTL_SECONDS) * 1000;
  const state = device.revoked_at !== null ? "REVOKED" : (!fresh ? "OFFLINE" : presence.state);
  return { device_id: device.id, friendly_label: device.friendly_label, credential_epoch: device.credential_epoch, state,
    protocol_version: device.protocol_version, runtime_version: device.runtime_version,
    endpoint_generation: presence?.endpoint_generation ?? null, endpoint_port: fresh ? presence?.endpoint_port ?? null : null,
    capabilities: presence ? JSON.parse(presence.capabilities_json) : {} };
}
function validCapabilities(value: unknown) { return isObject(value) && Object.keys(value).every(key => capabilities.has(key)); }

async function publishPresence(request: Request, env: Env) {
  const bodyBytes = new Uint8Array(await request.arrayBuffer());
  const device = await authenticateDevice(request, env, bodyBytes);
  let payload: unknown; try { payload = JSON.parse(new TextDecoder().decode(bodyBytes)); } catch { return error("MANIFEST_INVALID", 400); }
  if (!isObject(payload)) return error("MANIFEST_INVALID", 400);
  const allowed = new Set(["state", "protocol_version", "runtime_version", "endpoint_generation", "endpoint_port", "capabilities", "provider_metadata"]);
  if (Object.keys(payload).some(key => !allowed.has(key)) || payload.protocol_version !== protocolVersion || typeof payload.runtime_version !== "string" || !payload.runtime_version || typeof payload.endpoint_generation !== "string" || !payload.endpoint_generation || !states.has(String(payload.state)) || !validCapabilities(payload.capabilities) || !isObject(payload.provider_metadata) || hasForbidden(payload.provider_metadata) || (payload.endpoint_port !== undefined && (!Number.isInteger(payload.endpoint_port) || Number(payload.endpoint_port) < 1 || Number(payload.endpoint_port) > 65535))) return error("MANIFEST_INVALID", 400);
  const observedAt = nowMs();
  await env.DB.prepare("INSERT INTO device_presence(device_id,state,protocol_version,runtime_version,endpoint_generation,endpoint_port,capabilities_json,last_seen_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(device_id) DO UPDATE SET state=excluded.state,protocol_version=excluded.protocol_version,runtime_version=excluded.runtime_version,endpoint_generation=excluded.endpoint_generation,endpoint_port=excluded.endpoint_port,capabilities_json=excluded.capabilities_json,last_seen_at=excluded.last_seen_at").bind(device.id, payload.state, payload.protocol_version, payload.runtime_version, payload.endpoint_generation, payload.endpoint_port ?? null, JSON.stringify(payload.capabilities), observedAt).run();
  return json({ device_id: device.id, last_seen_at: new Date(observedAt).toISOString() });
}
async function publishManifest(request: Request, env: Env) {
  const bodyBytes = new Uint8Array(await request.arrayBuffer());
  const device = await authenticateDevice(request, env, bodyBytes);
  let payload: unknown; try { payload = JSON.parse(new TextDecoder().decode(bodyBytes)); } catch { return error("MANIFEST_INVALID", 400); }
  if (!isObject(payload) || hasForbidden(payload)) return error("FORBIDDEN_MANIFEST_CONTENT", 400);
  const allowed = new Set(["document_id", "filename", "size_bytes", "preparation_state", "index_state", "chunk_count", "artifact_id", "artifact_version", "artifact_profile_fingerprint", "local_availability", "error_code", "error_message"]);
  if (Object.keys(payload).some(key => !allowed.has(key)) || typeof payload.document_id !== "string" || typeof payload.preparation_state !== "string" || typeof payload.index_state !== "string" || typeof payload.local_availability !== "string") return error("MANIFEST_INVALID", 400);
  const columns = ["owner_user_id", "device_id", "document_id", "filename", "size_bytes", "preparation_state", "index_state", "chunk_count", "artifact_id", "artifact_version", "artifact_profile_fingerprint", "local_availability", "error_code", "error_message", "updated_at"];
  const updatedAt = nowMs();
  const values = [device.owner_user_id, device.id, payload.document_id, payload.filename ?? null, payload.size_bytes ?? null, payload.preparation_state, payload.index_state, payload.chunk_count ?? null, payload.artifact_id ?? null, payload.artifact_version ?? null, payload.artifact_profile_fingerprint ?? null, payload.local_availability, payload.error_code ?? null, payload.error_message ?? null, updatedAt];
  await env.DB.prepare(`INSERT INTO local_manifests(${columns.join(",")}) VALUES(${columns.map(() => "?").join(",")}) ON CONFLICT(owner_user_id,device_id,document_id) DO UPDATE SET filename=excluded.filename,size_bytes=excluded.size_bytes,preparation_state=excluded.preparation_state,index_state=excluded.index_state,chunk_count=excluded.chunk_count,artifact_id=excluded.artifact_id,artifact_version=excluded.artifact_version,artifact_profile_fingerprint=excluded.artifact_profile_fingerprint,local_availability=excluded.local_availability,error_code=excluded.error_code,error_message=excluded.error_message,updated_at=excluded.updated_at`).bind(...values).run();
  return json({ document_id: payload.document_id, device_id: device.id, updated_at: new Date(updatedAt).toISOString() });
}

export default { async fetch(request: Request, env: Env): Promise<Response> {
  const path = requestPath(request);
  if (path === "/health") return json({ status: "ok", service: "zkd-control-plane" });
  if (!path.startsWith("/api/")) return env.ASSETS.fetch(request);
  if (request.method === "OPTIONS") return new Response(null, { headers: { "access-control-allow-origin": env.PUBLIC_ORIGIN, "access-control-allow-credentials": "true", "access-control-allow-methods": "GET,POST,DELETE,OPTIONS" } });
  try {
    if (path === "/api/v1/auth/google/start" && request.method === "GET") {
      if (!env.GOOGLE_CLIENT_ID || !env.GOOGLE_CLIENT_SECRET) return oauthFailure("GOOGLE_CONFIGURATION_UNAVAILABLE");
      const state = random(), nonce = random(), verifier = random();
      const tx = b64url(bytes(JSON.stringify({ state, nonce, verifier, exp: unix() + 600 })));
      const authorization = new URL("https://accounts.google.com/o/oauth2/v2/auth");
      authorization.search = new URLSearchParams({ response_type: "code", client_id: env.GOOGLE_CLIENT_ID, redirect_uri: callbackUrl(env), scope: "openid email profile", state, nonce, code_challenge: await pkceChallenge(verifier), code_challenge_method: "S256" }).toString();
      console.info("google_auth_start"); return redirect(authorization.toString(), { "set-cookie": oauthCookie(tx, 600) });
    }
    if (path === "/api/v1/auth/google/callback" && request.method === "GET") {
      if (!env.GOOGLE_CLIENT_ID || !env.GOOGLE_CLIENT_SECRET) return oauthFailure("GOOGLE_CONFIGURATION_UNAVAILABLE");
      const txRaw = cookie(request, "zkd_google_tx"); const state = new URL(request.url).searchParams.get("state"); const code = new URL(request.url).searchParams.get("code");
      if (!txRaw || !state || !code) return oauthFailure("GOOGLE_STATE_INVALID");
      let tx: Record<string, unknown>; try { tx = decodeJson(txRaw); } catch { return oauthFailure("GOOGLE_STATE_INVALID"); }
      if (tx.exp !== undefined && (typeof tx.exp !== "number" || tx.exp < unix()) || typeof tx.state !== "string" || !fixedTimeEqual(bytes(state), bytes(tx.state)) || typeof tx.nonce !== "string" || typeof tx.verifier !== "string") return oauthFailure("GOOGLE_STATE_INVALID");
      try {
        const tokenResponse = await fetch("https://oauth2.googleapis.com/token", { method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" }, body: new URLSearchParams({ code, client_id: env.GOOGLE_CLIENT_ID, client_secret: env.GOOGLE_CLIENT_SECRET, redirect_uri: callbackUrl(env), grant_type: "authorization_code", code_verifier: tx.verifier }).toString() });
        if (!tokenResponse.ok) throw new Error("GOOGLE_AUTH_FAILED"); const token = await tokenResponse.json() as { id_token?: string }; if (typeof token.id_token !== "string") throw new Error("GOOGLE_AUTH_FAILED");
        const identity = await verifyGoogleIdToken(token.id_token, env, tx.nonce); const user = await resolveGoogleIdentity(env, identity.sub, identity.email); if (user.status !== "ACTIVE") throw new Error("GOOGLE_AUTH_FAILED"); const session = await createSession(env, user);
        console.info("google_auth_success", { user_id: user.id }); return redirectWithCookies("/", [cookieHeader(session, Number(env.SESSION_TTL_SECONDS)), oauthCookie("")]);
      } catch (failure) { return oauthFailure(failure instanceof Error && failure.message === "GOOGLE_ACCOUNT_LINK_CONFLICT" ? "GOOGLE_ACCOUNT_LINK_CONFLICT" : "GOOGLE_AUTH_FAILED"); }
    }
    if (path === "/api/v1/auth/login" && request.method === "POST") {
      const payload = await parseJson(request);
      if (!isObject(payload) || hasForbidden(payload) || Object.keys(payload).some(key => key !== "email" && key !== "password") || typeof payload.email !== "string" || typeof payload.password !== "string") return error("INVALID_CREDENTIALS", 401);
      const rate = await allowLogin(request, env, payload.email); if (!rate.allowed) return error("LOGIN_RATE_LIMITED", 429);
      const row = await env.DB.prepare("SELECT * FROM users WHERE lower(email)=lower(?)").bind(payload.email.trim()).first<any>();
      if (!row || row.status !== "ACTIVE" || !await verifyPassword(row.password_hash, payload.password)) { await recordFailedLogin(env, rate.key); return error("INVALID_CREDENTIALS", 401); }
      await env.DB.prepare("DELETE FROM login_rate_limits WHERE key_hash=?").bind(rate.key).run();
      const token = b64url(crypto.getRandomValues(new Uint8Array(32)));
      await env.DB.prepare("INSERT INTO sessions(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)").bind(await sha(token), row.id, nowMs() + Number(env.SESSION_TTL_SECONDS) * 1000, nowMs()).run();
      return json({ id: row.id, email: row.email, role: row.role, status: row.status, must_change_password: false }, 200, { "set-cookie": cookieHeader(token, Number(env.SESSION_TTL_SECONDS)) });
    }
    if (path === "/api/v1/auth/logout" && request.method === "POST") { const token = cookie(request, "zkd_session"); if (token) await env.DB.prepare("DELETE FROM sessions WHERE token_hash=?").bind(await sha(token)).run(); return new Response(null, { status: 204, headers: { "set-cookie": cookieHeader("") } }); }
    if (path === "/api/v1/auth/me" && request.method === "GET") {
      const principal = await inspectAuthMePrincipal(request, env);
      const result = principal.user ? 200 : 401;
      console.info("auth_me", { auth_me_cookie_present: principal.cookiePresent, auth_me_session_found: principal.sessionFound, auth_me_user_found: principal.userFound, auth_me_result: result });
      if (!principal.user) return error("AUTHENTICATION_REQUIRED", 401);
      return json({ ...principal.user, must_change_password: false });
    }
    if (path === "/api/v1/diagnostics/local-fetch" && request.method === "POST") {
      await requireUser(request, env);
      if (!sameOrigin(request, env)) return error("UNTRUSTED_ORIGIN", 403);
      const payload = await parseJson(request);
      if (!validLocalFetchDiagnostic(payload)) return error("DIAGNOSTIC_INVALID", 400);
      console.warn("local_fetch_diagnostic", payload);
      return new Response(null, { status: 204, headers: { "cache-control": "no-store" } });
    }

    if (path === "/api/v1/compute/pairing-challenges" && request.method === "POST") {
      const user = await requireUser(request, env); if (Number(request.headers.get("content-length") ?? "0") > 0) return error("PAIRING_INVALID", 400); const id = crypto.randomUUID(); const token = b64url(crypto.getRandomValues(new Uint8Array(32))); const code = String(Math.floor(Math.random() * 1_000_000)).padStart(6, "0"); const expiry = nowMs() + 300000;
      await env.DB.prepare("INSERT INTO pairing_challenges(id,owner_user_id,token_hash,confirmation_code_hash,state,expires_at,created_at) VALUES(?,?,?,?,?,?,?)").bind(id, user.id, await sha(token), await sha(code), "PENDING", expiry, nowMs()).run();
      return json({ pairing_request_id: id, pairing_token: token, confirmation_code: code, expires_at: new Date(expiry).toISOString() }, 201);
    }
    const confirm = path.match(/^\/api\/v1\/compute\/pairing-challenges\/([^/]+)\/confirm$/);
    if (confirm && request.method === "POST") {
      const user = await requireUser(request, env); const payload = await parseJson(request); const code = isObject(payload) && !hasForbidden(payload) && Object.keys(payload).length === 1 && typeof payload.confirmation_code === "string" ? payload.confirmation_code : "";
      const challenge = await env.DB.prepare("SELECT * FROM pairing_challenges WHERE id=? AND owner_user_id=?").bind(decodeURIComponent(confirm[1]), user.id).first<any>();
      if (!challenge || challenge.expires_at <= nowMs() || challenge.state !== "AWAITING_CONFIRMATION" || !fixedTimeEqual(bytes(await sha(code)), bytes(challenge.confirmation_code_hash))) return error("PAIRING_INVALID", 400);
      await env.DB.prepare("UPDATE pairing_challenges SET state='CONSUMED',confirmed_at=?,consumed_at=? WHERE id=?").bind(nowMs(), nowMs(), challenge.id).run();
      return json({ device_id: challenge.pending_device_id, state: "CONFIRMED" });
    }
    const complete = path.match(/^\/api\/v1\/compute\/control\/pairing-challenges\/([^/]+)\/complete$/);
    if (complete && request.method === "POST") {
      const payload = await parseJson(request);
      const pairingFields = new Set(["pairing_token", "public_key", "signature", "protocol_version", "runtime_version", "friendly_label"]);
      if (!isObject(payload) || hasForbidden(payload) || Object.keys(payload).some(key => !pairingFields.has(key)) || typeof payload.pairing_token !== "string" || typeof payload.public_key !== "string" || typeof payload.signature !== "string" || payload.protocol_version !== protocolVersion || typeof payload.runtime_version !== "string" || !payload.runtime_version || (payload.friendly_label !== undefined && typeof payload.friendly_label !== "string")) return error("PAIRING_INVALID", 400);
      const challenge = await env.DB.prepare("SELECT * FROM pairing_challenges WHERE id=?").bind(decodeURIComponent(complete[1])).first<any>();
      if (!challenge || !fixedTimeEqual(bytes(await sha(payload.pairing_token)), bytes(challenge.token_hash))) return error("PAIRING_INVALID", 400);
      if (challenge.expires_at <= nowMs()) { await env.DB.prepare("UPDATE pairing_challenges SET state='EXPIRED' WHERE id=?").bind(challenge.id).run(); return error("PAIRING_EXPIRED", 400); }
      if (challenge.state !== "PENDING") return error("PAIRING_ALREADY_CONSUMED", 400);
      try { const publicKey = await crypto.subtle.importKey("raw", b64decode(payload.public_key), { name: "Ed25519" }, false, ["verify"]); if (!await crypto.subtle.verify("Ed25519", publicKey, b64decode(payload.signature), bytes(`pairing|${challenge.id}|${payload.pairing_token}`))) throw new Error("invalid"); } catch { return error("DEVICE_AUTH_INVALID", 403); }
      const deviceId = crypto.randomUUID();
      await env.DB.batch([
        env.DB.prepare("INSERT INTO devices(id,owner_user_id,public_key_b64,friendly_label,protocol_version,runtime_version,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)").bind(deviceId, challenge.owner_user_id, payload.public_key, payload.friendly_label ?? null, protocolVersion, payload.runtime_version, nowMs(), nowMs()),
        env.DB.prepare("UPDATE pairing_challenges SET pending_device_id=?,state='AWAITING_CONFIRMATION' WHERE id=?").bind(deviceId, challenge.id),
      ]);
      return json({ device_id: deviceId, state: "AWAITING_CONFIRMATION", credential_epoch: 1 });
    }
    if (path === "/api/v1/compute/control/presence" && request.method === "POST") return await publishPresence(request, env);
    if (path === "/api/v1/compute/control/manifests" && request.method === "POST") return await publishManifest(request, env);
    if (path === "/api/v1/compute/devices" && request.method === "GET") { const user = await requireUser(request, env); const rows = await env.DB.prepare("SELECT * FROM devices WHERE owner_user_id=? ORDER BY created_at").bind(user.id).all<Device>(); return json({ devices: await Promise.all(rows.results.map(device => deviceState(env, device))) }); }
    const revoke = path.match(/^\/api\/v1\/compute\/devices\/([^/]+)\/revoke$/);
    if (revoke && request.method === "POST") { const user = await requireUser(request, env); const device = await env.DB.prepare("SELECT * FROM devices WHERE id=? AND owner_user_id=?").bind(decodeURIComponent(revoke[1]), user.id).first<Device>(); if (!device) return error("DEVICE_NOT_FOUND", 404); const epoch = device.credential_epoch + (device.revoked_at === null ? 1 : 0); await env.DB.prepare("UPDATE devices SET revoked_at=COALESCE(revoked_at,?),credential_epoch=?,updated_at=? WHERE id=?").bind(nowMs(), epoch, nowMs(), device.id).run(); return json({ device_id: device.id, state: "REVOKED", credential_epoch: epoch }); }
    const grant = path.match(/^\/api\/v1\/compute\/devices\/([^/]+)\/local-session-grants$/);
    if (grant && request.method === "POST") {
      const user = await requireUser(request, env); if (!sameOrigin(request, env)) return error("UNTRUSTED_ORIGIN", 403); const payload = await parseJson(request);
      if (!isObject(payload) || typeof payload.browser_nonce !== "string" || !payload.browser_nonce || Object.keys(payload).length !== 1) return error("LOCAL_SESSION_GRANT_UNAVAILABLE", 400);
      const device = await env.DB.prepare("SELECT * FROM devices WHERE id=? AND owner_user_id=?").bind(decodeURIComponent(grant[1]), user.id).first<Device>(); if (!device) return error("DEVICE_NOT_FOUND", 404);
      const state = await deviceState(env, device); if (state.state !== "READY" || !state.endpoint_generation) return error("DEVICE_OFFLINE", 503);
      const claims = { grant_id: crypto.randomUUID(), user_id: user.id, device_id: device.id, credential_epoch: device.credential_epoch, endpoint_generation: state.endpoint_generation, origin: env.PUBLIC_ORIGIN, browser_nonce: payload.browser_nonce, operations: grantOperations, exp: unix() + 300 };
      return json({ local_access_grant: await signGrant(env, claims), expires_at: claims.exp, device_id: device.id, endpoint_generation: state.endpoint_generation });
    }
    if (path === "/api/v1/compute/local-manifests" && request.method === "GET") {
      const user = await requireUser(request, env); const manifests = await env.DB.prepare("SELECT * FROM local_manifests WHERE owner_user_id=? ORDER BY updated_at DESC").bind(user.id).all<any>();
      const readModels = await Promise.all(manifests.results.map(async manifest => { const device = await env.DB.prepare("SELECT * FROM devices WHERE id=?").bind(manifest.device_id).first<Device>(); if (!device) return null; const state = await deviceState(env, device); const deviceCapabilities = state.capabilities; const retrievalAdmitted = ["READY", "ADMITTED"].includes(deviceCapabilities.retrieval); const artifactCompatible = !!(manifest.artifact_id && manifest.artifact_profile_fingerprint); return { document_id: manifest.document_id, device_id: manifest.device_id, preparation_state: manifest.preparation_state, index_state: manifest.index_state, local_availability: manifest.local_availability, artifact_id: manifest.artifact_id, artifact_profile_fingerprint: manifest.artifact_profile_fingerprint, device_state: state.state, retrieval_admitted: retrievalAdmitted, artifact_compatible: artifactCompatible, queryable: state.state === "READY" && retrievalAdmitted && manifest.preparation_state === "READY" && manifest.index_state === "READY" && manifest.local_availability === "AVAILABLE" && artifactCompatible, generation_available: ["READY", "ADMITTED"].includes(deviceCapabilities.generation) }; }));
      return json({ manifests: readModels.filter(Boolean) });
    }
    return error("NOT_FOUND", 404);
  } catch (failure) {
    if (failure instanceof ApiError) return error(failure.code, failure.status);
    // Preserve compatibility for any legacy helper that still throws a Response.
    if (failure instanceof Response || (failure && typeof failure === "object" && "status" in failure && "headers" in failure)) return failure as Response;
    console.error("control-plane failure", failure); return error("CONTROL_PLANE_UNAVAILABLE", 503);
  }
} };
