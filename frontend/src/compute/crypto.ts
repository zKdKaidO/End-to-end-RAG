/** Browser-compatible Web Crypto helpers for the frozen P2C.4A transcript. */
const encoder = new TextEncoder();

export function utf8(value: string): Uint8Array {
  return encoder.encode(value);
}

/** Copies into an ArrayBuffer accepted by the strict DOM Web Crypto typings. */
export function exactArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  const copy = new Uint8Array(bytes.byteLength);
  copy.set(bytes);
  return copy.buffer;
}

export function bytesToHex(bytes: ArrayBuffer | Uint8Array): string {
  return Array.from(bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes))
    .map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function sha256Hex(rawBody: Uint8Array): Promise<string> {
  return bytesToHex(await crypto.subtle.digest("SHA-256", exactArrayBuffer(rawBody)));
}

export function canonicalTranscript(method: string, path: string, timestamp: string, nonce: string, bodySha256: string): string {
  if (!path.startsWith("/") || path.includes("?") || path.includes("#")) {
    throw new Error("INVALID_REQUEST_PATH");
  }
  return [method.toUpperCase(), path, timestamp, nonce, bodySha256].join("|");
}

export async function hmacSha256Hex(sessionKey: string, transcript: string): Promise<string> {
  const key = await crypto.subtle.importKey("raw", exactArrayBuffer(utf8(sessionKey)), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return bytesToHex(await crypto.subtle.sign("HMAC", key, exactArrayBuffer(utf8(transcript))));
}

/** JSON.stringify is called exactly once. The returned bytes are both MACed and sent. */
export function serializeJsonOnce(payload: unknown): Uint8Array {
  const serialized = JSON.stringify(payload);
  if (serialized === undefined) throw new TypeError("JSON body must be serializable.");
  return utf8(serialized);
}

export async function binaryBodyBytes(value: Blob | ArrayBuffer | Uint8Array): Promise<Uint8Array> {
  if (value instanceof Uint8Array) return new Uint8Array(value);
  if (value instanceof ArrayBuffer) return new Uint8Array(value);
  return new Uint8Array(await value.arrayBuffer());
}

/** 32 CSPRNG bytes, URL-safe without padding; never persisted or reused. */
export function createBrowserNonce(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  let binary = "";
  bytes.forEach((value) => { binary += String.fromCharCode(value); });
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
