"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api";
import {
  saveToken,
  saveUser,
  getUser,
  removeToken,
  removeUser,
  getDashboardPath,
} from "@/lib/auth";
import type { User, UserRole } from "@/types";

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const stored = getUser();
    setUser(stored);
    setIsLoading(false);
  }, []);

  const login = useCallback(
    async (username: string, password: string): Promise<void> => {
      setIsLoading(true);
      try {
        const response = await authApi.login(username, password);
        const { access_token, user: userData } = response.data;
        saveToken(access_token);
        saveUser(userData);
        setUser(userData);
        router.push(getDashboardPath(userData.role));
      } catch (error: unknown) {
        const err = error as {
          response?: { data?: { detail?: string } };
          message?: string;
        };
        const message =
          err?.response?.data?.detail ||
          err?.message ||
          "Login failed. Please check your credentials.";
        throw new Error(message);
      } finally {
        setIsLoading(false);
      }
    },
    [router]
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // ignore errors on logout
    } finally {
      removeToken();
      removeUser();
      setUser(null);
      router.push("/login");
    }
  }, [router]);

  const isRole = useCallback(
    (...roles: UserRole[]): boolean => {
      if (!user) return false;
      return roles.includes(user.role);
    },
    [user]
  );

  return { user, isLoading, login, logout, isRole };
}
