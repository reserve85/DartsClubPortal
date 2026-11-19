import { Head, Link } from "@inertiajs/react";
import { Badge, Box, Button, Group, Paper, SimpleGrid, Stack, Text, UnstyledButton } from "@mantine/core";
import { IconCrown, IconList, IconPlus, IconSwords } from "@tabler/icons-react";
import { type Period, PeriodFilter } from "../../components/PeriodFilter";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { Delta, EmptyState, PageHeader } from "../../components/ui";
import { useFormat, useT, useTn } from "../../i18n";

export interface RankingEntry {
  playerId: number;
  name: string;
  avatar: string;
  position: number;
  elo: number;
  eloChange: number;
  positionChange: number | null;
  matches: number;
  wins: number;
  total180s: number;
  bestFinish: number | null;
  inactive: boolean;
  disabled: boolean;
}

interface Props {
  period: Period;
  includeInactive: boolean;
  entries: RankingEntry[];
  fieldSize: number;
  matchCount: number;
  myPlayerId: number | null;
  today: string;
}

const MEDALS = ["🥇", "🥈", "🥉"];

/**
 * Elo as shown in the ranking: whole numbers, but players who would look equal
 * get as many decimals as it takes to see who is ahead (up to two). Exactly
 * equal values stay whole numbers - there the head-to-head decides.
 */
function eloLabels(entries: RankingEntry[], f: ReturnType<typeof useFormat>) {
  const digits = (v: number) => {
    for (const d of [0, 1, 2]) {
      const same = entries.filter((x) => x.elo.toFixed(d) === v.toFixed(d)).length;
      if (same <= 1) return d;
    }
    return 0;
  };
  return (v: number) => {
    const d = digits(v);
    // Like every Elo value: no thousands separator (1612,4 - not 1.612,4).
    return d === 0 ? f.elo(v) : v.toFixed(d).replace(".", f.decimalSeparator);
  };
}

function Podium({ top, elo }: { top: RankingEntry[]; elo: (v: number) => string }) {
  const order = [top[1], top[0], top[2]];
  const heights = [72, 96, 56];
  return (
    <SimpleGrid cols={3} spacing="xs" mb="md" style={{ alignItems: "end" }}>
      {order.map((e, i) =>
        e ? (
          <UnstyledButton key={e.playerId} component={Link} href={`/elo/players/${e.playerId}/`} style={{ textAlign: "center" }}>
            <Stack gap={6} align="center">
              <PlayerAvatar name={e.name} src={e.avatar} size={i === 1 ? 76 : 58} style={{ boxShadow: "0 0 0 3px var(--mantine-color-body), 0 0 0 5px var(--mantine-color-dart-6)" }} />
              <Text fw={800} size="sm" truncate maw="100%">{e.name}</Text>
              <Paper
                w="100%"
                h={heights[i]}
                radius="md"
                style={{
                  display: "grid",
                  placeItems: "center",
                  background: i === 1 ? "linear-gradient(180deg, rgba(247,103,7,.35), rgba(247,103,7,.06))" : "var(--mantine-color-default-hover)",
                }}
              >
                <Text fw={900} className="num">{MEDALS[[1, 0, 2][i]]} {elo(e.elo)}</Text>
              </Paper>
            </Stack>
          </UnstyledButton>
        ) : (
          <div key={i} />
        ),
      )}
    </SimpleGrid>
  );
}

export function RankingRow({ e, me, periodQuery, elo }: { e: RankingEntry; me: boolean; periodQuery: string; elo?: (v: number) => string }) {
  const t = useT();
  const tn = useTn();
  const f = useFormat();
  const muted = e.disabled || (e.inactive && !e.matches);
  const sub = [
    e.matches ? `${tn("%(n)s match", "%(n)s matches", e.matches)} · ${e.wins} ${t("won")}` : t("no match in this period"),
    e.total180s ? `${e.total180s}×180` : "",
    e.bestFinish ? `HF ${e.bestFinish}` : "",
  ].filter(Boolean).join(" · ");
  return (
    <UnstyledButton
      component={Link}
      href={`/elo/players/${e.playerId}/?${periodQuery}`}
      px="md"
      py={10}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        borderBottom: "1px solid var(--mantine-color-default-border)",
        background: me ? "var(--mantine-color-brand-light)" : undefined,
        boxShadow: me ? "inset 3px 0 0 var(--mantine-color-brand-6)" : undefined,
        opacity: muted ? 0.6 : 1,
      }}
    >
      <Text w={26} ta="center" fw={800} c="dimmed" className="num">{e.position}</Text>
      <PlayerAvatar name={e.name} src={e.avatar} size={36} muted={e.disabled} />
      <Box style={{ flex: 1, minWidth: 0 }}>
        <Group gap={6} wrap="nowrap">
          <Text fw={700} truncate td={e.disabled ? "line-through" : undefined}>{e.name}</Text>
          {e.disabled && <Badge size="xs" color="red">{t("disabled")}</Badge>}
          {!e.disabled && e.inactive && <Badge size="xs" color="gray">{t("inactive")}</Badge>}
        </Group>
        <Text size="xs" c="dimmed" truncate>{sub}</Text>
      </Box>
      <Box ta="right">
        <Text fw={800} size="lg" className="num">{elo ? elo(e.elo) : f.elo(e.elo)}</Text>
        <Group gap={6} justify="flex-end" wrap="nowrap">
          <Delta value={e.eloChange} size="xs" />
          {e.positionChange ? (
            <Text span size="xs" fw={800} c={e.positionChange > 0 ? "teal" : "red"} className="num">
              {e.positionChange > 0 ? "↑" : "↓"}{Math.abs(e.positionChange)}
            </Text>
          ) : null}
        </Group>
      </Box>
    </UnstyledButton>
  );
}

export default function Ranking({ period, includeInactive, entries, fieldSize, matchCount, myPlayerId, today }: Props) {
  const t = useT();
  const tn = useTn();
  const f = useFormat();
  const elo = eloLabels(entries, f);
  const periodQuery = new URLSearchParams({ period: period.key, from: period.from, to: period.to }).toString();
  return (
    <>
      <Head title={t("Elo ranking")} />
      <PageHeader
        title={t("Elo ranking")}
        subtitle={`${f.date(period.from)} – ${f.date(period.to)} · ${tn("%(n)s match", "%(n)s matches", matchCount)}`}
        actions={
          <Button component={Link} href="/elo/matches/new/" leftSection={<IconPlus size={18} />} visibleFrom="sm">
            {t("Enter match")}
          </Button>
        }
      >
        <PeriodFilter period={period} today={today} includeInactive={includeInactive} />
      </PageHeader>

      {entries.length >= 3 && <Podium top={entries.slice(0, 3)} elo={elo} />}

      {entries.length ? (
        <Paper withBorder style={{ overflow: "hidden" }}>
          {entries.map((e) => (
            <RankingRow key={e.playerId} e={e} me={e.playerId === myPlayerId} periodQuery={periodQuery} elo={elo} />
          ))}
        </Paper>
      ) : (
        <EmptyState>{t("No players in the ranking for this period yet.")}</EmptyState>
      )}
      <Text size="xs" c="dimmed" mt="xs">
        {t("Positions count the full field of %(n)s players (inactive and disabled included).", { n: fieldSize })}
      </Text>

      <Group mt="md" gap="xs">
        <Button component={Link} href="/elo/head-to-head/" leftSection={<IconSwords size={16} />}>{t("Head-to-head")}</Button>
        <Button component={Link} href="/elo/all-time/" leftSection={<IconCrown size={16} />}>{t("All-time Elo")}</Button>
        <Button component={Link} href="/elo/matches/" leftSection={<IconList size={16} />}>{t("Matches")}</Button>
      </Group>

    </>
  );
}
