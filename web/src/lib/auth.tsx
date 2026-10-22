import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError, type MeOut, type UserRow } from "./api";

type AuthState = {
  me: MeOut | null;
  loading: boolean;
  user: UserRow | null;
  isAdmin: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const Ctx = createContext<AuthState>({
  me: null,
  loading: true,
  user: null,
  isAdmin: false,
  login: async () => undefined,
  logout: async () => undefined,
  refresh: async () => undefined,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<MeOut | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const res = await api.me();
      setMe(res);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setMe({ authenticated: false, user: null, csrf: "", ai_enabled: true });
      } else {
        setMe({ authenticated: false, user: null, csrf: "", ai_enabled: true });
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(
    async (username: string, password: string) => {
      const res = await api.login({ username, password });
      setMe({ authenticated: true, user: res.user, csrf: res.csrf, ai_enabled: true });
      await refresh();
    },
    [refresh],
  );

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setMe({ authenticated: false, user: null, csrf: "", ai_enabled: true });
    }
  }, []);

  const value = useMemo<AuthState>(() => {
    const user = me?.authenticated ? me.user : null;
    return {
      me,
      loading,
      user,
      isAdmin: !!user && (user.role === "admin" || user.role === "owner"),
      login,
      logout,
      refresh,
    };
  }, [me, loading, login, logout, refresh]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  return useContext(Ctx);
}
