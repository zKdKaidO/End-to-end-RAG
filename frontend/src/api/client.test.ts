import { describe, expect, it } from "vitest";
import { apiUrl, parseSseBlock } from "./client";

describe("same-origin API gateway", () => {
  it("prefixes non-versioned backend routes exactly once", () => {
    expect(apiUrl("/documents")).toBe("/api/documents");
    expect(apiUrl("/answer/stream")).toBe("/api/answer/stream");
  });

  it("preserves existing backend /api/v1 routes without a duplicate api segment", () => {
    expect(apiUrl("/api/v1/auth/me")).toBe("/api/v1/auth/me");
    expect(apiUrl("/api/v1/chat/sessions")).toBe("/api/v1/chat/sessions");
  });
});

describe("POST SSE parser", () => {
  it("parses start, delta, done, and error payloads", () => {
    expect(parseSseBlock('event: start\ndata: {"request_id":"r1"}')).toEqual({ event: "start", data: { request_id: "r1" } });
    expect(parseSseBlock('event: delta\ndata: {"text":"Xin chào"}')).toEqual({ event: "delta", data: { text: "Xin chào" } });
    expect(parseSseBlock('event: done\ndata: {"status":"COMPLETED"}')).toEqual({ event: "done", data: { status: "COMPLETED" } });
    expect(parseSseBlock('event: error\ndata: {"safe_message":"timeout"}')).toEqual({ event: "error", data: { safe_message: "timeout" } });
  });

  it("handles CRLF and ignores blocks without data", () => {
    expect(parseSseBlock('event: delta\r\ndata: {"text":"A"}\r\n')).toEqual({ event: "delta", data: { text: "A" } });
    expect(parseSseBlock("event: ping")).toBeNull();
  });
});
