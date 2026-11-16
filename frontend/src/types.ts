/** Shared Inertia props (see app/core/inertia_share.py). */
export interface NavItem {
  label: string;
  href: string;
  icon: string;
}
export interface NavGroup {
  key: string;
  label: string;
  hint?: string;
  icon: string;
  items: NavItem[];
}
export interface AuthUser {
  id: number;
  email: string;
  name: string;
  avatar: string;
  playerId: number | null;
  role: "system" | "admin" | "user" | null;
  isAdmin: boolean;
  isCaptain: boolean;
  captainOf: { id: number; name: string } | null;
  modules: { elo: boolean; penalty: boolean };
  theme: "auto" | "light" | "dark";
}
export interface SharedProps {
  site: {
    name: string;
    language: string;
    logo: { light: string; dark: string };
    build?: { version: string; commit: string; date: string; github: string; release: string };
  };
  auth: { user: AuthUser | null };
  nav: NavGroup[];
  i18n: Record<string, string>;
  urls: Record<string, string | null>;
  counts: { notifications?: number; approvals?: number };
  flash?: { messages?: { message: string; level: string; tags?: string }[] };
  errors?: Record<string, string[] | string>;
  [key: string]: unknown;
}
