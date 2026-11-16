import { Head, Link, router } from "@inertiajs/react";
import { AreaChart } from "@mantine/charts";
import { Badge, Box, Button, Grid, Group, Paper, Progress, Table, Text, UnstyledButton } from "@mantine/core";
import { IconPlus } from "@tabler/icons-react";
import { type PickPlayer, PlayerSelect } from "../../components/elo";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { Delta, EmptyState, PageHeader, Section } from "../../components/ui";
import { useFormat, useT, useTn } from "../../i18n";

interface Sum {
  player_id: number;
  name: string;
  avatar: string;
  current_elo: number;
  current_rank: number | null;
  wins: number;
  legs_won: number;
  elo_net: number;
  total_180s: number;
  best_high_finish: number | null;
  best_low_darts: number | null;
  average: number | null;
}
interface H2H {
  total_matches: number;
  a: Sum;
  b: Sum;
  win_probability_a: number;
  win_probability_b: number;
  streak: { player_id: number | null; count: number };
  first_meeting: string | null;
  last_meeting: string | null;
  recent: { id: number; date: string; winnerId: number; scoreA: number; scoreB: number; eloChangeA: number; avgA: number | null; avgB: number | null }[];
  timeline: { date: string; elo_balance_a: number }[];
}
interface Props {
  players: PickPlayer[];
  aId: number | null;
  bId: number | null;
  opponents: { id: number; name: string; matches: number }[];
  h2h: H2H | null;
}

export default function HeadToHead({ players, aId, bId, opponents, h2h }: Props) {
  const t = useT();
  const tn = useTn();
  const f = useFormat();
  const oppPlayers = opponents.map((o) => ({ ...players.find((p) => p.id === o.id)!, name: `${o.name} (${o.matches})` })).filter((p) => p.id);
  const go = (a: number | null, b: number | null) => router.get("/elo/head-to-head/", { ...(a ? { a } : {}), ...(b ? { b } : {}) }, { preserveScroll: true });
  const side = (s: Sum, color: string) => (
    <Box component={Link} href={`/elo/players/${s.player_id}/`} style={{ textDecoration: "none", color: "inherit", display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <PlayerAvatar name={s.name} src={s.avatar} size={72} color={color} />
      <Text fw={800} ta="center" lineClamp={2}>{s.name}</Text>
      <Text size="xs" c="dimmed">Elo {f.elo(s.current_elo)}{s.current_rank ? ` · #${s.current_rank}` : ""}</Text>
    </Box>
  );
  const row = (label: string, va: React.ReactNode, vb: React.ReactNode) => (
    <Table.Tr><Table.Td ta="center" fw={700} className="num">{va}</Table.Td><Table.Td ta="center"><Text size="xs" c="dimmed">{label}</Text></Table.Td><Table.Td ta="center" fw={700} className="num">{vb}</Table.Td></Table.Tr>
  );
  return (
    <>
      <Head title={t("Head-to-head")} />
      <PageHeader title={t("Head-to-head")}>
        <Grid gap="sm">
          <Grid.Col span={6}>
            <PlayerSelect label={t("Player")} players={players} value={aId} onChange={(id) => go(id, null)} placeholder={t("Choose player")} />
          </Grid.Col>
          <Grid.Col span={6}>
            <PlayerSelect label={t("Opponent")} players={oppPlayers} value={bId} onChange={(id) => go(aId, id)} disabled={!aId || !oppPlayers.length}
              placeholder={aId && !oppPlayers.length ? t("No direct match yet.") : t("Choose player")} />
          </Grid.Col>
        </Grid>
      </PageHeader>

      {!h2h ? (
        <EmptyState>{t("Choose two players who have played each other.")}</EmptyState>
      ) : (
        <>
          <Paper withBorder p="lg" className="hero">
            <Grid align="center" gap="xs">
              <Grid.Col span={4.5}>{side(h2h.a, "brand")}</Grid.Col>
              <Grid.Col span={3}>
                <Text ta="center" fw={900} fz={44} lh={1} className="num">
                  <Text span inherit c={h2h.a.wins > h2h.b.wins ? "teal" : undefined}>{h2h.a.wins}</Text>
                  <Text span inherit c="dimmed">:</Text>
                  <Text span inherit c={h2h.b.wins > h2h.a.wins ? "teal" : undefined}>{h2h.b.wins}</Text>
                </Text>
              </Grid.Col>
              <Grid.Col span={4.5}>{side(h2h.b, "dart")}</Grid.Col>
            </Grid>
            <Text ta="center" size="xs" c="dimmed" mt="xs">
              {tn("%(n)s match", "%(n)s matches", h2h.total_matches)}{h2h.first_meeting ? ` · ${f.date(h2h.first_meeting)} – ${f.date(h2h.last_meeting)}` : ""}
            </Text>
            <Text size="sm" fw={700} mt="md" mb={6}>{t("Win chance in the next match (Elo)")}</Text>
            <Progress.Root size={14} radius="xl">
              <Progress.Section value={h2h.win_probability_a * 100} color="brand" />
              <Progress.Section value={h2h.win_probability_b * 100} color="dart" />
            </Progress.Root>
            <Group justify="space-between" mt={4}>
              <Text size="sm" fw={800} className="num">{Math.round(h2h.win_probability_a * 100)} %</Text>
              <Text size="sm" fw={800} className="num">{Math.round(h2h.win_probability_b * 100)} %</Text>
            </Group>
            {h2h.streak.count > 1 && (
              <Group justify="center" mt="sm">
                <Badge size="lg" color="teal">🔥 {h2h.streak.player_id === h2h.a.player_id ? h2h.a.name : h2h.b.name} – {t("%(n)s wins in a row", { n: h2h.streak.count })}</Badge>
              </Group>
            )}
          </Paper>

          {h2h.total_matches > 0 && (
            <>
              <Paper withBorder p="md" mt="md">
                <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb="xs">{t("Comparison")}</Text>
                <Table verticalSpacing={6}>
                  <Table.Tbody>
                    {row(t("Legs"), h2h.a.legs_won, h2h.b.legs_won)}
                    {row(t("Elo won"), f.signed(h2h.a.elo_net), f.signed(h2h.b.elo_net))}
                    {row("Ø", h2h.a.average !== null ? f.number(h2h.a.average, 2) : "–", h2h.b.average !== null ? f.number(h2h.b.average, 2) : "–")}
                    {row("180er", h2h.a.total_180s || "–", h2h.b.total_180s || "–")}
                    {row(t("Best finish"), h2h.a.best_high_finish ?? "–", h2h.b.best_high_finish ?? "–")}
                    {row(t("Low darts"), h2h.a.best_low_darts ?? "–", h2h.b.best_low_darts ?? "–")}
                  </Table.Tbody>
                </Table>
              </Paper>
              {h2h.timeline.length > 1 && (
                <Paper withBorder p="md" mt="md">
                  <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb="xs">{t("Elo balance from %(name)s's view", { name: h2h.a.name })}</Text>
                  <AreaChart h={180} data={h2h.timeline.map((r) => ({ date: f.date(r.date), Elo: r.elo_balance_a }))} dataKey="date"
                    series={[{ name: "Elo", color: "brand.5" }]} curveType="monotone" gridAxis="y" tickLine="none" withDots={h2h.timeline.length < 30}
                    referenceLines={[{ y: 0, color: "gray.6" }]} yAxisProps={{ width: 34 }} valueFormatter={(v) => String(Math.round(v))} xAxisProps={{ minTickGap: 40 }} />
                </Paper>
              )}
              <Section title={t("Last meetings")}>
                <Paper withBorder style={{ overflow: "hidden" }}>
                  {h2h.recent.map((r) => {
                    const winner = r.winnerId === h2h.a.player_id ? h2h.a : h2h.b;
                    return (
                      <UnstyledButton key={r.id} component={Link} href={`/elo/matches/${r.id}/`} px="md" py={10}
                        style={{ display: "flex", alignItems: "center", gap: 12, borderBottom: "1px solid var(--mantine-color-default-border)" }}>
                        <PlayerAvatar name={winner.name} src={winner.avatar} size={30} />
                        <Box style={{ flex: 1 }}>
                          <Text fw={700}>{f.date(r.date)}</Text>
                          <Text size="xs" c="dimmed">Ø {r.avgA !== null ? f.number(r.avgA, 1) : "–"} / {r.avgB !== null ? f.number(r.avgB, 1) : "–"}</Text>
                        </Box>
                        <Box ta="right"><Text fw={900} className="num">{r.scoreA}:{r.scoreB}</Text><Delta value={r.eloChangeA} size="xs" /></Box>
                      </UnstyledButton>
                    );
                  })}
                </Paper>
              </Section>
            </>
          )}
          <Group mt="md">
            <Button component={Link} href={`/elo/matches/new/?a=${h2h.a.player_id}&b=${h2h.b.player_id}`} leftSection={<IconPlus size={16} />}>{t("Enter match")}</Button>
          </Group>
        </>
      )}
    </>
  );
}
