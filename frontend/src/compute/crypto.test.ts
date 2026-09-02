import vectors from "../../../tests/fixtures/browser_compute_hmac_v1.json";
import { describe, expect, it } from "vitest";
import { bytesToHex, canonicalTranscript, hmacSha256Hex, serializeJsonOnce, sha256Hex } from "./crypto";

function fromBase64(base64: string): Uint8Array {
  if (!base64) return new Uint8Array();
  return Uint8Array.from(atob(base64), (character) => character.charCodeAt(0));
}

describe("browser compute frozen HMAC vectors", () => {
  it.each(vectors.vectors)("matches $name byte-for-byte", async (vector) => {
    const body = fromBase64(vector.raw_body_base64);
    const bodyHash = await sha256Hex(body);
    const transcript = canonicalTranscript(vector.method, vector.path, vector.timestamp, vector.nonce, bodyHash);
    expect(bodyHash).toBe(vector.body_sha256);
    expect(transcript).toBe(vector.canonical_transcript);
    await expect(hmacSha256Hex(vector.session_secret, transcript)).resolves.toBe(vector.expected_hmac_sha256);
  });

  it("uses one UTF-8 JSON serialization as the sent/MACed body", async () => {
    const raw = serializeJsonOnce({ query_text: "doanh nghiệp", document_ids: ["11111111-1111-1111-1111-111111111111"] });
    expect(bytesToHex(raw)).toBe("7b2271756572795f74657874223a22646f616e68206e676869e1bb8770222c22646f63756d656e745f696473223a5b2231313131313131312d313131312d313131312d313131312d313131313131313131313131225d7d");
    await expect(sha256Hex(raw)).resolves.toBe("07c9ef2fe95b5db00ce0cc980753ed3ea78b32e54750af1001b489e73a51bf6f");
  });

  it("rejects a non-exact local path", () => {
    expect(() => canonicalTranscript("GET", "/v1/runtime?unsafe", "1", "n", "h")).toThrow("INVALID_REQUEST_PATH");
  });
});
