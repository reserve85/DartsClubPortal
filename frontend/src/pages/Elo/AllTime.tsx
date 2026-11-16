import { Head, Link, router } from "@inertiajs/react";
import { Box, Paper, Switch, Text, UnstyledButton } from "@mantine/core";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { EmptyState, PageHeader } from "../../components/ui";
import { useFormat, useT } from "../../i18n";

interface Row {
  playerId: number;
  name: string;
  avatar: string;
  maxElo: number;
  dateReached: string | null;
  inactive: boolean;
  disabled: boolean;
}

export default function AllTime({ rows, includeInactive }: { rows: Row[]; includeInactive: boolean }) {
  const t = useT();
  const f = useFormat();
  return (
    <>
      <Head title={t("All-time Elo")} />
      <PageHeader title={t("All-time Elo")} subtitle={t("The highest Elo every player ever reached.")}>
        <Switch
          checked={includeInactive}
          label={t("Show inactive and disabled players")}
          onChange={(e) => router.get("/elo/all-time/", { inactive: e.currentTarget.checked ? "1" : "0" }, { preserveState: true, preserveScroll: true, replace: true })}
        />
      </PageHeader>
      {rows.length ? (
        <Paper withBorder style={{ overflow: "hidden" }}>
          {rows.map((r, i) => (
            <UnstyledButton key={r.playerId} component={Link} href={`/elo/players/${r.playerId}/`} px="md" py={10}
              style={{ display: "flex", alignItems: "center", gap: 12, borderBottom: "1px solid var(--mantine-color-default-border)", opacity: r.disabled || r.inactive ? 0.6 : 1 }}>
              <Text w={26} ta="center" fw={800} c="dimmed" className="num">{i + 1}</Text>
              <PlayerAvatar name={r.name} src={r.avatar} size={36} muted={r.disabled} />
              <Box style={{ flex: 1, minWidth: 0 }}>
                <Text fw={700} truncate td={r.disabled ? "line-through" : undefined}>{r.name}</Text>
                <Text size="xs" c="dimmed">{r.dateReached ? f.date(r.dateReached) : t("start Elo")}</Text>
              </Box>
              <Text fw={800} size="lg" className="num">{f.elo(r.maxElo)}</Text>
            </UnstyledButton>
          ))}
        </Paper>
      ) : (
        <EmptyState>{t("No players yet.")}</EmptyState>
      )}
    </>
  );
}
