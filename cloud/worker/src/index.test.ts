import { afterEach, describe, expect, it, vi } from "vitest";

import worker, { importGrantSigningPrivateKey, signGrant } from "./index";

type User = { id: string; email: string; role: string; status: string };
type Session = { tokenHash: string; userId: string; expiresAt: number };

class Statement {
  values: unknown[] = [];

  constructor(private readonly database: FakeD1, readonly sql: string) {}

  bind(...values: unknown[]) { this.values = values; return this; }
  first<T>() { return Promise.resolve(this.database.first(this.sql, this.values) as T | null); }
  all<T>() { return Promise.resolve({ results: this.database.all(this.sql, this.values) as T[] }); }
  run() { return this.database.run(this.sql, this.values); }
}

class FakeD1 {
  readonly users = new Map<string, User>();
  readonly sessions = new Map<string, Session>();
  readonly identities = new Map<string, string>();
  readonly devices = new Map<string, Record<string, unknown>>();
  readonly presence = new Map<string, Record<string, unknown>>();
  readonly replayNonces = new Set<string>();

  prepare(sql: string) { return new Statement(this, sql); }
  async batch(statements: Statement[]) { for (const statement of statements) await statement.run(); return []; }

  first(sql: string, values: unknown[]) {
    if (sql.startsWith("SELECT u.id,u.email,u.role,u.status FROM user_identities")) {
      const userId = this.identities.get(String(values[0]));
      return userId ? this.users.get(userId) ?? null : null;
    }
    if (sql.startsWith("SELECT id,email,role,status FROM users WHERE lower(email)")) {
      const email = String(values[0]).toLowerCase();
      return [...this.users.values()].find((user) => user.email.toLowerCase() === email) ?? null;
    }
    if (sql.startsWith("SELECT u.id,u.email,u.role,u.status FROM sessions s JOIN users")) {
      const session = this.sessions.get(String(values[0]));
      return session && session.expiresAt > Number(values[1]) ? this.users.get(session.userId) ?? null : null;
    }
    if (sql.startsWith("SELECT user_id FROM sessions")) {
      const session = this.sessions.get(String(values[0]));
      return session && session.expiresAt > Number(values[1]) ? { user_id: session.userId } : null;
    }
    if (sql.startsWith("SELECT id,email,role,status FROM users WHERE id")) return this.users.get(String(values[0])) ?? null;
    if (sql.startsWith("SELECT * FROM devices WHERE id=? AND owner_user_id=?")) {
      const device = this.devices.get(String(values[0]));
      return device?.owner_user_id === String(values[1]) ? device : null;
    }
    if (sql.startsWith("SELECT * FROM devices WHERE id=?")) return this.devices.get(String(values[0])) ?? null;
    if (sql.startsWith("SELECT * FROM device_presence WHERE device_id=?")) return this.presence.get(String(values[0])) ?? null;
    if (sql.startsWith("SELECT 1 FROM replay_nonces")) return this.replayNonces.has(`${values[0]}:${values[1]}`) ? { value: 1 } : null;
    throw new Error(`Unhandled SELECT: ${sql}`);
  }

  all(_sql: string, _values: unknown[]) { return []; }

  async run(sql: string, values: unknown[]) {
    if (sql.startsWith("INSERT INTO user_identities")) { this.identities.set(String(values[1]), String(values[2])); return {}; }
    if (sql.startsWith("INSERT INTO sessions")) {
      this.sessions.set(String(values[0]), { tokenHash: String(values[0]), userId: String(values[1]), expiresAt: Number(values[2]) });
      return {};
    }
    if (sql.startsWith("DELETE FROM replay_nonces")) return {};
    if (sql.startsWith("INSERT INTO replay_nonces")) { this.replayNonces.add(`${values[0]}:${values[1]}`); return {}; }
    if (sql.startsWith("INSERT INTO device_presence") || sql.startsWith("INSERT INTO local_manifests")) return {};
    throw new Error(`Unhandled write: ${sql}`);
  }
}

const b64url = (value: Uint8Array | string) => btoa(typeof value === "string" ? value : String.fromCharCode(...value)).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");

async function googleIdToken(nonce: string, clientId: string) {
  const pair = await crypto.subtle.generateKey({ name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign", "verify"]);
  const header = b64url(JSON.stringify({ alg: "RS256", kid: "test-key" }));
  const payload = b64url(JSON.stringify({ iss: "https://accounts.google.com", aud: clientId, exp: Math.floor(Date.now() / 1000) + 300, iat: Math.floor(Date.now() / 1000), nonce, sub: "google-subject", email: "alice@example.com", email_verified: true }));
  const signed = `${header}.${payload}`;
  const signature = new Uint8Array(await crypto.subtle.sign("RSASSA-PKCS1-v1_5", pair.privateKey, new TextEncoder().encode(signed)));
  const jwk = await crypto.subtle.exportKey("jwk", pair.publicKey);
  return { token: `${signed}.${b64url(signature)}`, jwk: { ...jwk, kid: "test-key", alg: "RS256", use: "sig" } };
}

const controlEnv = (database: FakeD1) => ({
  DB: database,
  ASSETS: { fetch: vi.fn() },
  PUBLIC_ORIGIN: "https://rag.zkd.id.vn",
  SESSION_TTL_SECONDS: "2592000",
  PRESENCE_TTL_SECONDS: "90",
  GRANT_SIGNING_PRIVATE_KEY_B64: "unused",
});

const b64 = (value: Uint8Array) => btoa(String.fromCharCode(...value));
const fromB64url = (value: string) => Uint8Array.from(atob(value.replaceAll("-", "+").replaceAll("_", "/") + "=".repeat((4 - value.length % 4) % 4)), (char) => char.charCodeAt(0));
const fromHex = (value: string) => Uint8Array.from(value.match(/../g)!.map((part) => Number.parseInt(part, 16)));
const grantSeed = fromHex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60");
const grantPublic = fromHex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a");
const grantSecret = b64(grantSeed);
const grantEnv = (database: FakeD1) => ({ ...controlEnv(database), GRANT_SIGNING_PRIVATE_KEY_B64: grantSecret });
async function sessionHash(token: string) { return b64url(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(token)))); }

async function signedControlRequest(path: string, deviceId: string, privateKey: CryptoKey, payload: object, nonce: string) {
  const body = JSON.stringify(payload);
  const timestamp = String(Math.floor(Date.now() / 1000));
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(body)));
  const digestHex = Array.from(digest, (byte) => byte.toString(16).padStart(2, "0")).join("");
  const transcript = new TextEncoder().encode(["POST", path, "1", timestamp, nonce, digestHex].join("|"));
  const signature = new Uint8Array(await crypto.subtle.sign("Ed25519", privateKey, transcript));
  return new Request(`https://rag.zkd.id.vn${path}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "X-ZKD-Device-ID": deviceId,
      "X-ZKD-Credential-Epoch": "1",
      "X-ZKD-Timestamp": timestamp,
      "X-ZKD-Nonce": nonce,
      "X-ZKD-Signature": b64(signature),
    },
    body,
  });
}

describe("Google OAuth callback session cookies", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("keeps session and transaction-clear cookies distinct and authenticates the callback session", async () => {
    const database = new FakeD1();
    const user = { id: "user-1", email: "alice@example.com", role: "USER", status: "ACTIVE" };
    database.users.set(user.id, user);
    const clientId = "test-google-client";
    const state = "state-value", nonce = "nonce-value", verifier = "verifier-value";
    const { token, jwk } = await googleIdToken(nonce, clientId);
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "https://oauth2.googleapis.com/token") return new Response(JSON.stringify({ id_token: token }));
      if (url === "https://www.googleapis.com/oauth2/v3/certs") return new Response(JSON.stringify({ keys: [jwk] }));
      throw new Error(`Unexpected fetch: ${url}`);
    }));
    const transaction = b64url(JSON.stringify({ state, nonce, verifier, exp: Math.floor(Date.now() / 1000) + 600 }));
    const env = {
      DB: database,
      ASSETS: { fetch: vi.fn() },
      PUBLIC_ORIGIN: "https://staging.zkd.id.vn",
      SESSION_TTL_SECONDS: "2592000",
      PRESENCE_TTL_SECONDS: "90",
      GRANT_SIGNING_PRIVATE_KEY_B64: "unused",
      GOOGLE_CLIENT_ID: clientId,
      GOOGLE_CLIENT_SECRET: "test-secret",
    };
    const callback = await worker.fetch(new Request(`https://staging.zkd.id.vn/api/v1/auth/google/callback?code=code&state=${state}`, { headers: { cookie: `zkd_google_tx=${transaction}` } }), env as never);

    expect(callback.status).toBe(302);
    expect(callback.headers.get("location")).toBe("/");
    const cookies = callback.headers.getSetCookie();
    expect(cookies).toHaveLength(2);
    const sessionCookie = cookies.find((value) => value.startsWith("zkd_session="));
    const transactionClearCookie = cookies.find((value) => value.startsWith("zkd_google_tx="));
    expect(sessionCookie).toMatch(/^zkd_session=[^;]+; Path=\/; HttpOnly; Secure; SameSite=Lax; Max-Age=2592000$/);
    expect(transactionClearCookie).toBe("zkd_google_tx=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0");
    expect(sessionCookie).not.toContain(",");
    expect(transactionClearCookie).not.toContain(",");
    expect(cookies.join(";")).not.toMatch(/Domain=/i);

    const sessionValue = sessionCookie!.split(";")[0].slice("zkd_session=".length);
    const authMeLog = vi.spyOn(console, "info").mockImplementation(() => undefined);
    const authMe = await worker.fetch(new Request("https://staging.zkd.id.vn/api/v1/auth/me", { headers: { cookie: `zkd_session=${sessionValue}` } }), env as never);
    expect(authMe.status).toBe(200);
    expect(await authMe.json()).toMatchObject({ id: user.id, email: user.email, role: "USER", status: "ACTIVE" });
    expect(authMeLog).toHaveBeenCalledWith("auth_me", { auth_me_cookie_present: true, auth_me_session_found: true, auth_me_user_found: true, auth_me_result: 200 });
  });
});

describe("installed Compute control-channel response contract", () => {
  it("returns legacy-compatible JSON objects for presence and manifest success", async () => {
    const database = new FakeD1();
    const deviceId = "device-1";
    const pair = await crypto.subtle.generateKey({ name: "Ed25519" }, true, ["sign", "verify"]);
    const publicKey = new Uint8Array(await crypto.subtle.exportKey("raw", pair.publicKey));
    database.devices.set(deviceId, { id: deviceId, owner_user_id: "user-1", public_key_b64: b64(publicKey), credential_epoch: 1, revoked_at: null, protocol_version: "zkd-compute-v1", runtime_version: "0.1.0", friendly_label: null });
    const presence = await worker.fetch(await signedControlRequest(
      "/api/v1/compute/control/presence", deviceId, pair.privateKey,
      { state: "READY", protocol_version: "zkd-compute-v1", runtime_version: "0.1.0", endpoint_generation: "generation-1", endpoint_port: 43123, capabilities: {}, provider_metadata: {} },
      "presence-nonce",
    ), controlEnv(database) as never);
    expect(presence.status).toBe(200);
    expect(await presence.json()).toEqual({ device_id: deviceId, last_seen_at: expect.any(String) });

    const manifest = await worker.fetch(await signedControlRequest(
      "/api/v1/compute/control/manifests", deviceId, pair.privateKey,
      { document_id: "document-1", preparation_state: "READY", index_state: "READY", local_availability: "AVAILABLE" },
      "manifest-nonce",
    ), controlEnv(database) as never);
    expect(manifest.status).toBe(200);
    expect(await manifest.json()).toEqual({ document_id: "document-1", device_id: deviceId, updated_at: expect.any(String) });
  });

  it("returns a JSON DEVICE_NOT_FOUND object rather than a Worker primitive/error page", async () => {
    const database = new FakeD1();
    const pair = await crypto.subtle.generateKey({ name: "Ed25519" }, true, ["sign", "verify"]);
    const response = await worker.fetch(await signedControlRequest(
      "/api/v1/compute/control/presence", "missing-device", pair.privateKey,
      { state: "READY", protocol_version: "zkd-compute-v1", runtime_version: "0.1.0", endpoint_generation: "generation-1", capabilities: {}, provider_metadata: {} },
      "missing-device-nonce",
    ), controlEnv(database) as never);
    expect(response.status).toBe(404);
    expect(await response.json()).toEqual({ detail: { error_code: "DEVICE_NOT_FOUND", message: "DEVICE NOT FOUND" } });
  });
});

describe("local session grant signing", () => {
  it("wraps the documented 32-byte seed as PKCS#8 and signs data verifiable by its known public key", async () => {
    const claims = { grant_id: "grant-1", user_id: "user-1", device_id: "device-1", credential_epoch: 1, endpoint_generation: "generation-1", origin: "https://rag.zkd.id.vn", browser_nonce: "nonce-1", operations: ["documents"], exp: 1_800_000_000 };
    const grant = await signGrant({ GRANT_SIGNING_PRIVATE_KEY_B64: grantSecret } as Env, claims);
    const [raw, signature] = grant.split(".");
    const publicKey = await crypto.subtle.importKey("raw", grantPublic, { name: "Ed25519" }, false, ["verify"]);

    expect(await crypto.subtle.verify("Ed25519", publicKey, fromB64url(signature), new TextEncoder().encode(raw))).toBe(true);
    expect(JSON.parse(new TextDecoder().decode(fromB64url(raw)))).toEqual(claims);
  });

  it("rejects malformed or non-32-byte signing secrets without returning secret material", async () => {
    for (const invalid of ["not*base64", b64(new Uint8Array(31)), b64(new Uint8Array(33)), `${grantSecret}\n`]) {
      await expect(importGrantSigningPrivateKey(invalid)).rejects.toThrow("GRANT_SIGNING_KEY_INVALID");
    }
  });

  it("returns a cryptographically valid BrowserComputeClient grant for an owned READY device", async () => {
    const database = new FakeD1();
    const user = { id: "user-1", email: "alice@example.com", role: "USER", status: "ACTIVE" };
    const deviceId = "device-1";
    const session = "test-session";
    database.users.set(user.id, user);
    database.sessions.set(await sessionHash(session), { tokenHash: await sessionHash(session), userId: user.id, expiresAt: Date.now() + 60_000 });
    database.devices.set(deviceId, { id: deviceId, owner_user_id: user.id, public_key_b64: b64(grantPublic), credential_epoch: 7, revoked_at: null, protocol_version: "zkd-compute-v1", runtime_version: "0.1.0", friendly_label: null });
    database.presence.set(deviceId, { device_id: deviceId, state: "READY", endpoint_generation: "generation-7", endpoint_port: 43123, capabilities_json: "{}", last_seen_at: Date.now() });

    const response = await worker.fetch(new Request(`https://rag.zkd.id.vn/api/v1/compute/devices/${deviceId}/local-session-grants`, {
      method: "POST",
      headers: { "content-type": "application/json", origin: "https://rag.zkd.id.vn", cookie: `zkd_session=${session}` },
      body: JSON.stringify({ browser_nonce: "browser-nonce-1" }),
    }), grantEnv(database) as never);

    expect(response.status).toBe(200);
    const payload = await response.json() as { local_access_grant: string; expires_at: number; device_id: string; endpoint_generation: string };
    expect(payload).toEqual({ local_access_grant: expect.any(String), expires_at: expect.any(Number), device_id: deviceId, endpoint_generation: "generation-7" });
    const [raw, signature] = payload.local_access_grant.split(".");
    const publicKey = await crypto.subtle.importKey("raw", grantPublic, { name: "Ed25519" }, false, ["verify"]);
    expect(await crypto.subtle.verify("Ed25519", publicKey, fromB64url(signature), new TextEncoder().encode(raw))).toBe(true);
    expect(JSON.parse(new TextDecoder().decode(fromB64url(raw)))).toMatchObject({ user_id: user.id, device_id: deviceId, credential_epoch: 7, endpoint_generation: "generation-7", origin: "https://rag.zkd.id.vn", browser_nonce: "browser-nonce-1", operations: ["documents", "jobs", "retrieval", "answer"] });
  });
});

describe("sanitized browser local-fetch diagnostics", () => {
  it("accepts an authenticated, same-origin, exact allowlisted answer diagnostic without D1 writes", async () => {
    const database = new FakeD1();
    const user = { id: "user-1", email: "alice@example.com", role: "USER", status: "ACTIVE" };
    const session = "test-session";
    database.users.set(user.id, user);
    database.sessions.set(await sessionHash(session), { tokenHash: await sessionHash(session), userId: user.id, expiresAt: Date.now() + 60_000 });
    const warning = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const payload = { operation: "answers", phase: "actual-fetch", exception_name: "TypeError", exception_message: "LOCAL_FETCH_NETWORK_REJECTED", host_type: "loopback", method: "POST", endpoint_path: "/v1/answers", local_session_present: true, browser_nonce_present: false, abort_signal_fired: false, request_timeout_configured: false, frontend_state: "AUTHENTICATED_REQUEST", classification: "BROWSER_NETWORK_REJECTED" };

    const response = await worker.fetch(new Request("https://rag.zkd.id.vn/api/v1/diagnostics/local-fetch", {
      method: "POST", headers: { "content-type": "application/json", origin: "https://rag.zkd.id.vn", cookie: `zkd_session=${session}` }, body: JSON.stringify(payload),
    }), controlEnv(database) as never);

    expect(response.status).toBe(204);
    expect(warning).toHaveBeenCalledWith("local_fetch_diagnostic", payload);
  });

  it("rejects diagnostic payloads containing arbitrary exception text", async () => {
    const database = new FakeD1();
    const user = { id: "user-1", email: "alice@example.com", role: "USER", status: "ACTIVE" };
    const session = "test-session";
    database.users.set(user.id, user);
    database.sessions.set(await sessionHash(session), { tokenHash: await sessionHash(session), userId: user.id, expiresAt: Date.now() + 60_000 });
    const response = await worker.fetch(new Request("https://rag.zkd.id.vn/api/v1/diagnostics/local-fetch", {
      method: "POST", headers: { "content-type": "application/json", origin: "https://rag.zkd.id.vn", cookie: `zkd_session=${session}` },
      body: JSON.stringify({ operation: "answers", exception_message: "user query must never be accepted" }),
    }), controlEnv(database) as never);

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({ detail: { error_code: "DIAGNOSTIC_INVALID" } });
  });

  it("accepts only fixed-schema transport probe and request-construction diagnostics", async () => {
    const database = new FakeD1();
    const user = { id: "user-1", email: "alice@example.com", role: "USER", status: "ACTIVE" };
    const session = "test-session";
    database.users.set(user.id, user);
    database.sessions.set(await sessionHash(session), { tokenHash: await sessionHash(session), userId: user.id, expiresAt: Date.now() + 60_000 });
    const warning = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const base = { method: "POST", headers: { "content-type": "application/json", origin: "https://rag.zkd.id.vn", cookie: `zkd_session=${session}` } };
    const probe = { operation: "transport_probe", probe_id: "P3", success: true, exception_name: "None", classification: "PROBE_SUCCEEDED" };
    const preparation = { operation: "answer_request_preparation", body_type: "ArrayBuffer", body_byte_length: 14, body_detached: false, request_construction: "SUCCEEDED", exception_name: "None", classification: "REQUEST_CONSTRUCTION_SUCCEEDED", header_validity: { origin: true, "content-type": true, "x-zkd-local-session": true, "x-zkd-timestamp": true, "x-zkd-nonce": true, "x-zkd-mac": true, "x-zkd-protocol-version": true } };

    for (const payload of [probe, preparation]) {
      const response = await worker.fetch(new Request("https://rag.zkd.id.vn/api/v1/diagnostics/local-fetch", { ...base, body: JSON.stringify(payload) }), controlEnv(database) as never);
      expect(response.status).toBe(204);
    }
    expect(warning).toHaveBeenCalledWith("local_fetch_diagnostic", probe);
    expect(warning).toHaveBeenCalledWith("local_fetch_diagnostic", preparation);
  });
});
