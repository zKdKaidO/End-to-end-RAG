import { useCallback, useEffect, useRef, useState } from "react";

const STREAM_COMMIT_INTERVAL_MS = 48;

export interface StreamRenderStats {
  incomingDeltas: number;
  visibleCommits: number;
  cadenceMs: number;
}

export function useBufferedStream() {
  const textRef = useRef("");
  const timerRef = useRef<number | null>(null);
  const incomingDeltasRef = useRef(0);
  const visibleCommitsRef = useRef(0);
  const [visibleText, setVisibleText] = useState("");
  const [stats, setStats] = useState<StreamRenderStats>({
    incomingDeltas: 0,
    visibleCommits: 0,
    cadenceMs: STREAM_COMMIT_INTERVAL_MS,
  });

  const cancelScheduledCommit = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const commit = useCallback(() => {
    timerRef.current = null;
    visibleCommitsRef.current += 1;
    setVisibleText(textRef.current);
    setStats({
      incomingDeltas: incomingDeltasRef.current,
      visibleCommits: visibleCommitsRef.current,
      cadenceMs: STREAM_COMMIT_INTERVAL_MS,
    });
  }, []);

  const append = useCallback((text: string) => {
    if (!text) return;
    textRef.current += text;
    incomingDeltasRef.current += 1;
    if (timerRef.current === null) {
      timerRef.current = window.setTimeout(commit, STREAM_COMMIT_INTERVAL_MS);
    }
  }, [commit]);

  const reset = useCallback(() => {
    cancelScheduledCommit();
    textRef.current = "";
    incomingDeltasRef.current = 0;
    visibleCommitsRef.current = 0;
    setVisibleText("");
    setStats({ incomingDeltas: 0, visibleCommits: 0, cadenceMs: STREAM_COMMIT_INTERVAL_MS });
  }, [cancelScheduledCommit]);

  const finish = useCallback((authoritativeText?: string) => {
    cancelScheduledCommit();
    if (authoritativeText !== undefined) textRef.current = authoritativeText;
    visibleCommitsRef.current += 1;
    setVisibleText(textRef.current);
    setStats({
      incomingDeltas: incomingDeltasRef.current,
      visibleCommits: visibleCommitsRef.current,
      cadenceMs: STREAM_COMMIT_INTERVAL_MS,
    });
  }, [cancelScheduledCommit]);

  useEffect(() => cancelScheduledCommit, [cancelScheduledCommit]);

  return { visibleText, append, finish, reset, stats };
}
