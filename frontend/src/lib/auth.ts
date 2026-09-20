import Cookies from "js-cookie";
import type { User, UserRole } from "@/types";

const TOKEN_KEY = "acadtrack_token";
const USER_KEY = "acadtrack_user";

export function saveToken(token: string): void {
  Cookies.set(TOKEN_KEY, token, { expires: 1, sameSite: "strict" });
}

export function getToken(): string | undefined {
  return Cookies.get(TOKEN_KEY);
}

export function removeToken(): void {
  Cookies.remove(TOKEN_KEY);
}

export function saveUser(user: User): void {
  if (typeof window !== "undefined") {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }
}

export function getUser(): User | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function removeUser(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem(USER_KEY);
  }
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

export function getUserRole(): UserRole | null {
  const user = getUser();
  return user ? user.role : null;
}

export function getDashboardPath(role: UserRole): string {
  switch (role) {
    case "super_admin":
      return "/dashboard/overview";
    case "controller":
      return "/dashboard/transcripts";
    case "hod":
      return "/dashboard/analytics";
    case "coordinator":
      return "/dashboard/upload";
    case "student":
      return "/portal";
    default:
      return "/dashboard/overview";
  }
}
