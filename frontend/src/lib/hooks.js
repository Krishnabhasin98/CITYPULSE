import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Minimal data hook: one loading flag, one error, one refresh function.
 * Replaces the ad-hoc useEffect/Promise.all blocks that left pages stuck on
 * "Loading..." forever whenever a request failed.
 */
export function useApiData(fetcher, deps = [], { skip = false, initial = null } = {}) {
  const [data, setData] = useState(initial);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(!skip);
  const mounted = useRef(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const load = useCallback(async () => {
    if (skip) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const result = await fetcherRef.current();
      if (mounted.current) {
        setData(result);
        setError(null);
      }
    } catch (err) {
      if (mounted.current) setError(err);
    } finally {
      if (mounted.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skip, ...deps]);

  useEffect(() => {
    load();
  }, [load]);

  return { data, error, loading, reload: load, setData };
}

/** Debounce any fast-changing value (search boxes, sliders). */
export function useDebounced(value, delay = 350) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

/** Close a popover/drawer on outside click or Escape. */
export function useDismiss(ref, onDismiss) {
  useEffect(() => {
    const handleClick = (event) => {
      if (ref.current && !ref.current.contains(event.target)) onDismiss();
    };
    const handleKey = (event) => {
      if (event.key === "Escape") onDismiss();
    };
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [ref, onDismiss]);
}

/** Copy-to-clipboard with a short "Copied" state, no dependency needed. */
export function useCopy(timeout = 1800) {
  const [copied, setCopied] = useState(false);
  const copy = useCallback(
    async (text) => {
      try {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), timeout);
        return true;
      } catch {
        return false;
      }
    },
    [timeout],
  );
  return { copied, copy };
}
