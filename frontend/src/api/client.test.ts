import { describe, expect, it } from "vitest";
import { parseSseBlock } from "./client";

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
