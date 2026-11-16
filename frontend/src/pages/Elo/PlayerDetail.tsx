import { Head, Link, router } from "@inertiajs/react";
import { AreaChart } from "@mantine/charts";
import { Badge, Box, Button, Group, Paper, Select, SimpleGrid, Table, Text, UnstyledButton } from "@mantine/core";
import { IconEdit, IconSwords } from "@tabler/icons-react";
import { useState } from "react";
import { type Period, PeriodFilter } from "../../components/PeriodFilter";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { Delta, EmptyState, PageHeader, Section, StatGrid, StatTile } from "../../components/ui";
import { useFormat, useT } from "../../i18n";

interface Agg {
  matches: number;
  wins: number;
  losses: number;
  legs_won: number;
  legs_lost: number;
  total_180s: number;
  high_finishes: number[];
  low_darts: number[];
  average: number | null;
  win_rate: number | null;
  average_last100?: number | null;
}
interface Props {
  player: { id: number; name: string; avatar: string; elo: number; entryDate: string; disabled: boolean };
  rank: number | null;
  fieldSize: number;
  ath: { elo: number; date: string | null };
  best: { rank: number | null; date: string | null };
  period: Period;
  today: string;
  stats: { period: Agg; all_time: Agg };
  eloHistory: { date: string; elo: number; match_id: number }[];
  avgHistory: { date: string; average: number; rolling: number; match_id: number }[];
  opponents: { id: number; name: string; wins: number; losses: number; matches: number }[];
  recent: { id: number; date: string; won: boolean; me: number; opp: number; oppName: string; change: number }[];
  canEdit: boolean;
}

export default function PlayerDetail(p: Props) {
  const t = useT();
  const f = useFormat();
  const [vs, setVs] = useState<string | null>(p.opponents[0] ? String(p.opponents[0].id) : null);
  const kv = (label: string, value: React.ReactNode) => (
    <Table.Tr><Table.Td c="dimmed">{label}</Table.Td><Table.Td ta="right" fw={700} className="num">{value}</Table.Td></Table.Tr>
  );
  const s = p.stats.period;
  const a = p.stats.all_time;
  return (
    <>
      <Head title={p.player.name} />
      <PageHeader
        left={<PlayerAvatar name={p.player.name} src={p.player.avatar} size={64} muted={p.player.disabled} />}
        title={<Text inherit td={p.player.disabled ? "line-through" : undefined}>{p.player.name}</Text>}
        subtitle={
          <Group gap={6} component="span">
            {p.rank && <Badge color="brand" variant="filled">#{p.rank} / {p.fieldSize}</Badge>}
            <Badge color="gray">{t("since %(d)s", { d: f.date(p.player.entryDate) })}</Badge>
            {p.player.disabled && <Badge color="red">{t("disabled")}</Badge>}
          </Group>
        }
        actions={p.canEdit && <Button color="yellow" component={Link} href={`/elo/manage/players/${p.player.id}/edit/`} leftSection={<IconEdit size={16} />}>{t("Edit")}</Button>}
      >
        <StatGrid>
          <StatTile label={t("Elo")} value={f.elo(p.player.elo)} color="brand" />
          <StatTile label={t("Best Elo")} value={f.elo(p.ath.elo)} />
          <StatTile label={t("Best rank")} value={p.best.rank ? `#${p.best.rank}` : "–"} />
        </StatGrid>
      </PageHeader>

      <Paper withBorder p="md">
        <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb="sm">{t("Elo history")}</Text>
        {p.eloHistory.length > 1 ? (
          <AreaChart h={200} data={p.eloHistory.map((r) => ({ date: f.date(r.date), Elo: r.elo }))} dataKey="date" series={[{ name: "Elo", color: "brand.5" }]}
            curveType="monotone" withDots={p.eloHistory.length < 40} gridAxis="y" tickLine="none" yAxisProps={{ domain: ["dataMin - 20", "dataMax + 20"], width: 40 }} valueFormatter={(v) => String(Math.round(v))} xAxisProps={{ minTickGap: 40 }} />
        ) : <Text c="dimmed" size="sm">{t("Not enough matches yet.")}</Text>}
      </Paper>

      <Paper withBorder p="md" mt="md">
        <PeriodFilter period={p.period} today={p.today} showInactiveSwitch={false} />
        <Box mt="md">
          <StatGrid>
            <StatTile label={t("Matches")} value={`${s.wins}–${s.losses}`} />
            <StatTile label={t("Legs")} value={`${s.legs_won}:${s.legs_lost}`} />
            <StatTile label="Ø" value={s.average !== null ? f.number(s.average, 2) : "–"} />
          </StatGrid>
        </Box>
        <Table mt="sm" verticalSpacing={6}>
          <Table.Tbody>
            {kv(t("Win rate"), s.win_rate !== null ? `${s.win_rate} %` : "–")}
            {kv("180er", s.total_180s || "–")}
            {kv(t("High finishes"), s.high_finishes.join(", ") || "–")}
            {kv(t("Low darts"), s.low_darts.join(", ") || "–")}
          </Table.Tbody>
        </Table>
      </Paper>

      <SimpleGrid cols={{ base: 1, sm: 2 }} mt="md" spacing="md">
        <Paper withBorder p="md">
          <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb="xs">{t("All time")}</Text>
          <Table verticalSpacing={6}>
            <Table.Tbody>
              {kv(t("Matches"), `${a.matches} (${a.wins}–${a.losses})`)}
              {kv(t("Win rate"), a.win_rate !== null ? `${a.win_rate} %` : "–")}
              {kv(t("Legs"), `${a.legs_won}:${a.legs_lost}`)}
              {kv("180er", a.total_180s || "–")}
              {kv(t("Best finish"), a.high_finishes[0] ?? "–")}
              {kv(t("Best low darts"), a.low_darts[0] ?? "–")}
              {kv(t("Average"), a.average !== null ? f.number(a.average, 2) : "–")}
              {kv(t("Average (last 100)"), a.average_last100 ? f.number(a.average_last100, 2) : "–")}
              {kv(t("Best Elo reached"), f.date(p.ath.date))}
              {kv(t("Best rank reached"), f.date(p.best.date))}
            </Table.Tbody>
          </Table>
        </Paper>
        <Paper withBorder p="md">
          <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb="xs">{t("Average history")} · Ø 5</Text>
          {p.avgHistory.length > 1 ? (
            <AreaChart h={240} data={p.avgHistory.map((r) => ({ date: f.date(r.date), "Ø": r.rolling }))} dataKey="date" series={[{ name: "Ø", color: "dart.6" }]}
              curveType="monotone" withDots={false} gridAxis="y" tickLine="none" yAxisProps={{ domain: ["dataMin - 3", "dataMax + 3"], width: 34 }} valueFormatter={(v) => String(Math.round(v))} xAxisProps={{ minTickGap: 40 }} />
          ) : <Text c="dimmed" size="sm">{t("Not enough matches yet.")}</Text>}
        </Paper>
      </SimpleGrid>

      <Paper withBorder p="md" mt="md">
        <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb="xs">{t("Head-to-head")}</Text>
        {p.opponents.length ? (
          <Group gap="xs" wrap="nowrap">
            <Select style={{ flex: 1 }} value={vs} onChange={setVs} searchable aria-label={t("Opponent")}
              data={p.opponents.map((o) => ({ value: String(o.id), label: `${o.name} (${o.wins}–${o.losses})` }))} />
            <Button leftSection={<IconSwords size={16} />} disabled={!vs} onClick={() => router.get("/elo/head-to-head/", { a: p.player.id, b: vs })}>{t("Compare")}</Button>
          </Group>
        ) : <Text c="dimmed" size="sm">{t("No direct match yet.")}</Text>}
      </Paper>

      <Section title={t("Last matches")} right={<Button size="xs" component={Link} href={`/elo/matches/?player=${p.player.id}`}>{t("All matches")}</Button>}>
        {p.recent.length ? (
          <Paper withBorder style={{ overflow: "hidden" }}>
            {p.recent.map((m) => (
              <UnstyledButton key={m.id} component={Link} href={`/elo/matches/${m.id}/`} px="md" py={10}
                style={{ display: "flex", alignItems: "center", gap: 12, borderBottom: "1px solid var(--mantine-color-default-border)" }}>
                <Badge color={m.won ? "teal" : "red"} variant="filled" w={28} p={0}>{m.won ? t("W") : t("L")}</Badge>
                <Box style={{ flex: 1, minWidth: 0 }}>
                  <Text fw={700} truncate>{t("vs %(opp)s", { opp: m.oppName })}</Text>
                  <Text size="xs" c="dimmed">{f.date(m.date)}</Text>
                </Box>
                <Box ta="right">
                  <Text fw={900} className="num">{m.me}:{m.opp}</Text>
                  <Delta value={m.change} size="xs" />
                </Box>
              </UnstyledButton>
            ))}
          </Paper>
        ) : <EmptyState>{t("No matches yet.")}</EmptyState>}
      </Section>
    </>
  );
}
