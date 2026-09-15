import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { apiGet, apiPost, endpoints, getToken, setToken } from "./api";

const SessionContext = createContext(null);

const USER_KEY = "citypulse_user";

function readStoredUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || "null");
  } catch {
    return null;
  }
}

function storeUser(user) {
  try {
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
    else localStorage.removeItem(USER_KEY);
  } catch {
    /* ignore storage failures */
  }
}

export function SessionProvider({ children }) {
  const [user, setUser] = useState(() => (getToken() ? readStoredUser() : null));
  const [meta, setMeta] = useState(null);
  const [metaError, setMetaError] = useState(null);
  const [ready, setReady] = useState(false);

  const loadMeta = useCallback(async () => {
    try {
      const data = await apiGet(endpoints.meta());
      setMeta(data);
      setMetaError(null);
      return data;
    } catch (error) {
      setMetaError(error);
      return null;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      await loadMeta();
      if (getToken()) {
        try {
          const profile = await apiGet(endpoints.me());
          if (!cancelled) {
            setUser(profile);
            storeUser(profile);
          }
        } catch (error) {
          if (error.status === 401) {
            // Token expired or the secret changed: drop it quietly.
            setToken(null);
            storeUser(null);
            if (!cancelled) setUser(null);
          }
        }
      }
      if (!cancelled) setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [loadMeta]);

  const applySession = useCallback((payload) => {
    setToken(payload.access_token);
    const nextUser = {
      user_id: payload.user_id,
      name: payload.name,
      email: payload.email,
      role: payload.role,
      credits: payload.credits,
      reputation: payload.reputation,
      ward: payload.ward,
    };
    setUser(nextUser);
    storeUser(nextUser);
    return nextUser;
  }, []);

  const login = useCallback(
    async (email, password) => {
      const payload = await apiPost(endpoints.login(), { email, password });
      const nextUser = applySession(payload);
      apiGet(endpoints.me()).then((profile) => {
        setUser(profile);
        storeUser(profile);
      }).catch(() => {});
      return nextUser;
    },
    [applySession],
  );

  const register = useCallback(
    async (details) => {
      const payload = await apiPost(endpoints.register(), details);
      return applySession(payload);
    },
    [applySession],
  );

  const demoLogin = useCallback(
    async (role = "citizen") => {
      const payload = await apiPost(endpoints.demoSession(role));
      return applySession(payload);
    },
    [applySession],
  );

  const logout = useCallback(() => {
    setToken(null);
    storeUser(null);
    setUser(null);
  }, []);

  const refreshProfile = useCallback(async () => {
    if (!getToken()) return null;
    try {
      const profile = await apiGet(endpoints.me());
      setUser(profile);
      storeUser(profile);
      return profile;
    } catch {
      return null;
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      meta,
      metaError,
      ready,
      isAuthenticated: Boolean(user),
      isAuthority: Boolean(user?.role && ["authority", "admin"].includes(user.role)),
      login,
      register,
      demoLogin,
      logout,
      refreshProfile,
      reloadMeta: loadMeta,
    }),
    [user, meta, metaError, ready, login, register, demoLogin, logout, refreshProfile, loadMeta],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession must be used inside <SessionProvider>");
  return context;
}
