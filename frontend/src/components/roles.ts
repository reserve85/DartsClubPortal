import { useT } from "../i18n";

type Scope = "elo" | "penalty" | "portal";

/** One label for an account's role: an admin of only some areas is "Elo admin" etc., not "Admin". */
export function useRoleLabel() {
  const t = useT();
  const scopeLabel: Record<Scope, string> = { elo: t("Elo admin"), penalty: t("Penalty admin"), portal: t("Portal admin") };
  return (role: string | null | undefined, scopes: Scope[] = []): string => {
    if (role === "system") return t("System");
    if (role === "admin") {
      const own = (["elo", "penalty", "portal"] as Scope[]).filter((s) => scopes.includes(s));
      return own.length === 0 || own.length === 3 ? t("Admin") : own.map((s) => scopeLabel[s]).join(" · ");
    }
    if (role === "club") return t("Club account");
    if (role === "user") return t("User");
    return t("no role");
  };
}
