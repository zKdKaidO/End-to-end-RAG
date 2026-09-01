#!/usr/bin/env node
/* Browser-compatible, dependency-free P2C.5C.1A reference only; never bundled. */
import { createHmac, createHash } from "node:crypto";
import { readFile } from "node:fs/promises";

export function canonicalTranscript(method, path, timestamp, nonce, rawBody) {
  const bodyHash = createHash("sha256").update(rawBody).digest("hex");
  return `${method.toUpperCase()}|${path}|${timestamp}|${nonce}|${bodyHash}`;
}

export function requestMac(sessionSecret, method, path, timestamp, nonce, rawBody) {
  return createHmac("sha256", sessionSecret)
    .update(canonicalTranscript(method, path, timestamp, nonce, rawBody), "utf8")
    .digest("hex");
}

if (process.argv[2]) {
  const fixture = JSON.parse(await readFile(process.argv[2], "utf8"));
  const output = fixture.vectors.map((vector) => {
    const body = Buffer.from(vector.raw_body_base64, "base64");
    return {
      name: vector.name,
      body_sha256: createHash("sha256").update(body).digest("hex"),
      canonical_transcript: canonicalTranscript(vector.method, vector.path, vector.timestamp, vector.nonce, body),
      expected_hmac_sha256: requestMac(vector.session_secret, vector.method, vector.path, vector.timestamp, vector.nonce, body),
    };
  });
  process.stdout.write(`${JSON.stringify(output)}\n`);
}
