import { Head, Link, usePage } from "@inertiajs/react";
import { Badge, Box, Button, Group, Paper, SimpleGrid, Stack, Text, UnstyledButton } from "@mantine/core";
import { IconCoins, IconPlus, IconTrophy } from "@tabler/icons-react";
import { BalanceTiles } from "../components/BalanceTiles";
import { CalendarSubscribe, type CalendarLink } from "../components/CalendarSubscribe";
import { PlayerAvatar } from "../components/PlayerAvatar";
import { Delta, EmptyState, PageHeader, StatGrid, StatTile } from "../components/ui";
import { useFormat, useT } from "../i18n";
import type { SharedProps } from "../types";

interface Props {
  elo: {
    top: { playerId: number; name: string; avatar: string; position: number; elo: number; eloChange: number }[];
    me: { playerId: number; elo: number; position: number | null; monthChange: number; recent: { id: number; date: string; won: boolean; oppName: string; me: number; opp: number }[] } | null;
  } | null;
  penalty: { me: boolean | null; season?: string; total?: number; paid?: number; balance?: number } | null;
  nextMatchdays: NextTeam[];
  calendars: CalendarLink[];
  today: string;
}
interface NextTeam {
  team: string;
  own: boolean;
  matchdays: { id: number; date: string; time: string; opponent: string; venue: string; home: boolean; location: string; url: string | null }[];
}

/** Next matchdays of every team: the next two weeks, at least the next one; own teams first. */
function NextMatchdays({ teams, calendars }: { teams: NextTeam[]; calendars: CalendarLink[] }) {
  const t = useT();
  const f = useFormat();
  return (
    <Paper withBorder p="md">
      <Group justify="space-between" mb="sm" gap="xs">
        <Text fw={800}>📅 {t("Next matchdays")}</Text>
        <Group gap={6}>
          <Button size="xs" component={Link} href="/schedule/">{t("Schedule")}</Button>
          <CalendarSubscribe calendars={calendars} size="xs" />
        </Group>
      </Group>
      <Stack gap="xs">
        {teams.map((team) => (
          <Paper
            key={team.team}
            p="xs"
            radius="md"
            withBorder
            style={team.own ? { background: "var(--mantine-color-brand-light)", boxShadow: "inset 3px 0 0 var(--mantine-color-brand-6)" } : undefined}
          >
            <Group gap={6} mb={4}>
              <Text fw={800} size="sm">{team.team}</Text>
              {team.own && <Badge size="xs" color="brand">{t("my team")}</Badge>}
            </Group>
            {team.matchdays.map((m) => {
              const line = (
                <Group gap={8} wrap="nowrap" align="flex-start">
                  <Text size="sm" fw={700} className="num" w={92} style={{ flexShrink: 0 }}>
                    {f.date(m.date)}{m.time ? ` ${m.time}` : ""}
                  </Text>
                  <Box style={{ minWidth: 0 }}>
                    <Text size="sm" truncate>
                      <Badge size="xs" variant="light" color="brand" mr={6}>{m.venue}</Badge>
                      {m.opponent}
                    </Text>
                    {m.location && <Text size="xs" c="dimmed" truncate>{m.location}</Text>}
                  </Box>
                </Group>
              );
              return m.url ? (
                <UnstyledButton key={m.id} component={Link} href={m.url} display="block" py={2}>{line}</UnstyledButton>
              ) : (
                <Box key={m.id} py={2}>{line}</Box>
              );
            })}
          </Paper>
        ))}
      </Stack>
    </Paper>
  );
}

const row = { display: "flex", alignItems: "center", gap: 12, borderBottom: "1px solid var(--mantine-color-default-border)" } as const;

export default function Overview({ elo, penalty, nextMatchdays, calendars, today }: Props) {
  const t = useT();
  const f = useFormat();
  const { auth } = usePage<SharedProps>().props;
  const user = auth.user!;
  return (
    <>
      <Head title={t("My overview")} />
      <PageHeader left={<PlayerAvatar name={user.name} src={user.avatar} size={56} />} title={t("Hello %(name)s", { name: user.name })} subtitle={f.date(today)} />
      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
        {elo && (
          <Paper withBorder p="md">
            <Group justify="space-between" mb="sm">
              <Text fw={800}>🎯 Elo</Text>
              <Button size="xs" component={Link} href="/elo/matches/new/" leftSection={<IconPlus size={14} />}>{t("Enter match")}</Button>
            </Group>
            {elo.me && (
              <>
                <StatGrid>
                  <StatTile label={t("Elo")} value={f.elo(elo.me.elo)} color="brand" />
                  <StatTile label={t("Position")} value={elo.me.position ? `#${elo.me.position}` : "–"} />
                  <StatTile label={t("This month")} value={f.signed(elo.me.monthChange)} color={elo.me.monthChange >= 0 ? "teal" : "red"} />
                </StatGrid>
                {elo.me.recent.length > 0 && (
                  <Paper withBorder mt="sm" style={{ overflow: "hidden" }}>
                    {elo.me.recent.map((m) => (
                      <UnstyledButton key={m.id} component={Link} href={`/elo/matches/${m.id}/`} px="md" py={8} style={row}>
                        <Badge color={m.won ? "teal" : "red"} variant="filled" w={28} p={0}>{m.won ? t("W") : t("L")}</Badge>
                        <Box style={{ flex: 1, minWidth: 0 }}><Text fw={700} truncate>{t("vs %(opp)s", { opp: m.oppName })}</Text><Text size="xs" c="dimmed">{f.date(m.date)}</Text></Box>
                        <Text fw={900} className="num">{m.me}:{m.opp}</Text>
                      </UnstyledButton>
                    ))}
                  </Paper>
                )}
              </>
            )}
            {elo.top.length > 0 && (
              <>
                <Text size="xs" fw={800} tt="uppercase" c="dimmed" mt="md" mb={6}>{t("Top of the month")}</Text>
                <Paper withBorder style={{ overflow: "hidden" }}>
                  {elo.top.map((e) => (
                    <UnstyledButton key={e.playerId} component={Link} href={`/elo/players/${e.playerId}/`} px="md" py={8} style={row}>
                      <Text w={20} fw={800} c="dimmed" className="num">{e.position}</Text>
                      <PlayerAvatar name={e.name} src={e.avatar} size={30} />
                      <Text fw={700} style={{ flex: 1 }} truncate>{e.name}</Text>
                      <Box ta="right"><Text fw={800} className="num">{f.elo(e.elo)}</Text><Delta value={e.eloChange} size="xs" /></Box>
                    </UnstyledButton>
                  ))}
                </Paper>
              </>
            )}
            <Group mt="md" gap="xs">
              <Button size="xs" component={Link} href="/elo/" leftSection={<IconTrophy size={14} />}>{t("Ranking")}</Button>
              {elo.me && <Button size="xs" component={Link} href={`/elo/players/${elo.me.playerId}/`}>{t("My statistics")}</Button>}
            </Group>
          </Paper>
        )}
        {penalty && (
          <Paper withBorder p="md">
            <Group justify="space-between" mb="sm">
              <Text fw={800}>💶 Penalty</Text>
              {penalty.season && <Badge>{penalty.season}</Badge>}
            </Group>
            {penalty.me ? (
              <BalanceTiles total={penalty.total ?? 0} paid={penalty.paid ?? 0} balance={penalty.balance ?? 0} />
            ) : (
              <Text c="dimmed" size="sm">{t("Your account is not linked to a player yet.")}</Text>
            )}
            <Group mt="md">
              <Button size="xs" component={Link} href="/financial/" leftSection={<IconCoins size={14} />}>{t("Financial overview")}</Button>
            </Group>
          </Paper>
        )}
        {nextMatchdays.length > 0 && <NextMatchdays teams={nextMatchdays} calendars={calendars} />}
        {!elo && !penalty && <EmptyState>{t("No module is available for your account. Please contact an administrator.")}</EmptyState>}
      </SimpleGrid>
    </>
  );
}
