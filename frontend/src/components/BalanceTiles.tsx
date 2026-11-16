import { useFormat, useT } from "../i18n";
import { StatGrid, StatTile } from "./ui";

/** Penalties total / settled / open (or credit when negative). */
export function BalanceTiles({ total, paid, balance }: { total: number; paid: number; balance: number }) {
  const t = useT();
  const f = useFormat();
  return (
    <StatGrid>
      <StatTile label={t("Penalties total")} value={f.euro(total)} color="red" />
      <StatTile label={t("Penalties settled")} value={f.euro(paid)} color="teal" />
      {balance < 0 ? (
        <StatTile label={t("Credit")} value={f.euro(Math.abs(balance))} color="teal" />
      ) : (
        <StatTile label={t("Penalties open")} value={f.euro(balance)} color={balance > 0 ? "red" : undefined} />
      )}
    </StatGrid>
  );
}
