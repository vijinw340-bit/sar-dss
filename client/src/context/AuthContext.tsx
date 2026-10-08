import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { User } from "@/types";
import { apiGet, apiPost } from "@/lib/api";

interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem("sar_token")
  );
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const stored = localStorage.getItem("sar_token");
    if (!stored) {
      setLoading(false);
      return;
    }
    try {
      const me = await apiGet<User>("/auth/me");
      setUser(me);
      localStorage.setItem("sar_user", JSON.stringify(me));
    } catch {
      setUser(null);
      localStorage.removeItem("sar_token");
      localStorage.removeItem("sar_user");
      setToken(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const cached = localStorage.getItem("sar_user");
    if (cached) {
      try {
        setUser(JSON.parse(cached));
      } catch {
        /* ignore */
      }
    }
    void refresh();
  }, [refresh]);

  const login = useCallback(async (username: string, password: string) => {
    const res = await apiPost<{ access_token: string; user: User }>("/auth/login", {
      username,
      password,
    });
    localStorage.setItem("sar_token", res.access_token);
    localStorage.setItem("sar_user", JSON.stringify(res.user));
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("sar_token");
    localStorage.removeItem("sar_user");
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
