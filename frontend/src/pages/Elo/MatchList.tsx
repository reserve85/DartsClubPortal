import { Head, Link, router } from "@inertiajs/react";
import { Box, Button, Grid, Group, Pagination, Paper, Text, UnstyledButton } from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { IconDownload, IconPlus } from "@tabler/icons-react";
import dayjs from "dayjs";
import { PlayerSelect } from "../../components/elo";
import { EmptyState, PageHeader } from "../../components/ui";
import { useFormat, useT, useTn } from "../../i18n";

export interface MatchRow {
  id: number;
  date: string;
  bestOf: number;
  a: { id: number; name: string; avatar: string };
  b: { id: number; name: string; avatar: string };
  scoreA: number;
  scoreB: number;
  winnerId: number;
  avgA: number | null;
  avgB: number | null;
}
interface Props {
  matches: MatchRow[];
  page: number;
  pages: number;
  total: number;
  filters: { player: string; from: string; to: string };
  players: { id: number; name: string }[];
  isAdmin: boolean;
  today: string;
}

export function MatchLine({ m }: { m: MatchRow }) {
  const t = useT();
  const f = useFormat();
  const avg = m.avgA !== null || m.avgB !== null ? ` · Ø ${m.avgA !== null ? f.number(m.avgA, 1) : "–"} / ${m.avgB !== null ? f.number(m.avgB, 1) : "–"}` : "";
  return (
    <UnstyledButton component={Link} href={`/elo/matches/${m.id}/`} px="md" py={10} style={{ display: "flex", alignItems: "center", gap: 12, borderBottom: "1px solid var(--mantine-color-default-border)" }}>
      <Box style={{ flex: 1, minWidth: 0 }}>
        <Text fw={700} truncate>
          <Text span inherit c={m.winnerId === m.a.id ? "teal" : undefined}>{m.a.name}</Text>
          <Text span c="dimmed"> – </Text>
          <Text span inherit c={m.winnerId === m.b.id ? "teal" : undefined}>{m.b.name}</Text>
        </Text>
        <Text size="xs" c="dimmed">{f.date(m.date)} · {t("Best of %(n)s", { n: m.bestOf })}{avg}</Text>
      </Box>
      <Text fw={900} size="lg" className="num">{m.scoreA}:{m.scoreB}</Text>
    </UnstyledButton>
  );
}

export default function MatchList({ matches, page, pages, total, filters, players, isAdmin, today }: Props) {
  const t = useT();
  const tn = useTn();
  const apply = (next: Partial<Props["filters"]> & { page?: number }) =>
    router.get("/elo/matches/", { ...filters, page: 1, ...next }, { preserveState: true, preserveScroll: !("player" in next || "from" in next), replace: true });
  return (
    <>
      <Head title={t("Matches")} />
      <PageHeader
        title={t("Matches")}
        subtitle={tn("%(n)s match", "%(n)s matches", total)}
        actions={<Button component={Link} href="/elo/matches/new/" leftSection={<IconPlus size={18} />}>{t("Enter match")}</Button>}
      >
        <Grid gap="sm">
          <Grid.Col span={{ base: 12, sm: 6 }}>
            <PlayerSelect
              label={t("Player")}
              placeholder={t("All players")}
              players={players}
              value={filters.player ? Number(filters.player) : null}
              onChange={(id) => apply({ player: id ? String(id) : "" })}
              clearable
              allowDeselect
            />
          </Grid.Col>
          <Grid.Col span={{ base: 12, sm: 6 }}>
            <DatePickerInput
              type="range"
              label={t("Period")}
              clearable
              allowSingleDateInRange
              maxDate={today}
              value={[filters.from || null, filters.to || null]}
              onChange={(v) => {
                const [a, b] = v as [string | null, string | null];
                if ((a && b) || (!a && !b)) apply({ from: a ? dayjs(a).format("YYYY-MM-DD") : "", to: b ? dayjs(b).format("YYYY-MM-DD") : "" });
              }}
            />
          </Grid.Col>
        </Grid>
      </PageHeader>
      {matches.length ? (
        <Paper withBorder style={{ overflow: "hidden" }}>
          {matches.map((m) => <MatchLine key={m.id} m={m} />)}
        </Paper>
      ) : (
        <EmptyState>{t("No matches found.")}</EmptyState>
      )}
      {pages > 1 && (
        <Group justify="center" mt="md">
          <Pagination total={pages} value={page} onChange={(p) => apply({ page: p } as never)} siblings={1} boundaries={1} />
        </Group>
      )}
      {isAdmin && (
        <Group mt="md">
          <Button component="a" href="/elo/export/matches.csv" leftSection={<IconDownload size={16} />}>{t("Matches as CSV")}</Button>
        </Group>
      )}
    </>
  );
}
