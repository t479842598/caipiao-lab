import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError, type MeOut, type UserRow } from "./api";

type AuthState = {
  me: MeOut | null;
  loading: boolean;
  user: UserRow | null;
  isAdmin: boolean;
  /** 已登录（管理员或普通用户） */
  isAuthed: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, displayName?: string) => Promise<number>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const Ctx = createContext<AuthState>({
  me: null,
  loading: true,
  user: null,
  isAdmin: false,
  isAuthed: false,
  login: async () => undefined,
  register: async () => 0,
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

  const register = useCallback(
    async (username: string, password: string, displayName?: string) => {
      const res = await api.register({ username, password, display_name: displayName || undefined });
      setMe({ authenticated: true, user: res.user, csrf: res.csrf, ai_enabled: true });
      // 注册后把本设备上以游客身份存的票迁到新账号，避免用户丢数据
      let moved = 0;
      try {
        const claimed = await api.claimTickets();
        moved = claimed.moved;
      } catch {
        // 迁移失败不影响注册本身，用户仍可在票夹页手动触发
      }
      await refresh();
      return moved;
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
      isAuthed: !!user,
      login,
      register,
      logout,
      refresh,
    };
  }, [me, loading, login, register, logout, refresh]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  return useContext(Ctx);
}
