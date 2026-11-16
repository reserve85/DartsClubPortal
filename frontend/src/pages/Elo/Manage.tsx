import { Head, Link } from "@inertiajs/react";
import { ActionIcon, Badge, Box, Button, Group, Paper, SimpleGrid, Text, Tooltip } from "@mantine/core";
import { IconCalculator, IconDownload, IconEdit, IconPlayerPlay, IconPlus, IconUserOff } from "@tabler/icons-react";
import { confirmPost } from "../../components/elo";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { EmptyState, PageHeader, Section } from "../../components/ui";
import { useFormat, useT, useTn } from "../../i18n";

interface P {
  id: number;
  name: string;
  elo: number;
  startElo: number;
  avatar: string;
  disabled: boolean;
  entryDate: string;
}

export default function Manage({ players, matchTotal }: { players: P[]; matchTotal: number }) {
  const t = useT();
  const tn = useTn();
  const f = useFormat();
  return (
    <>
      <Head title={t("Elo administration")} />
      <PageHeader
        title={t("Elo administration")}
        subtitle={`${tn("%(n)s player", "%(n)s players", players.length)} · ${tn("%(n)s match", "%(n)s matches", matchTotal)}`}
        actions={<Button component={Link} href="/elo/manage/players/add/" leftSection={<IconPlus size={18} />}>{t("Add player")}</Button>}
      />
      <Section title={t("Players")}>
        {players.length ? (
          <Paper withBorder style={{ overflow: "hidden" }}>
            {players.map((p) => (
              <Group key={p.id} px="md" py={10} wrap="nowrap" gap="sm" style={{ borderBottom: "1px solid var(--mantine-color-default-border)", opacity: p.disabled ? 0.65 : 1 }}>
                <PlayerAvatar name={p.name} src={p.avatar} size={36} muted={p.disabled} />
                <Box style={{ flex: 1, minWidth: 0 }} component={Link} href={`/elo/players/${p.id}/`} c="inherit" td="none">
                  <Group gap={6} wrap="nowrap">
                    <Text fw={700} truncate td={p.disabled ? "line-through" : undefined}>{p.name}</Text>
                    {p.disabled && <Badge size="xs" color="red">{t("disabled")}</Badge>}
                  </Group>
                  <Text size="xs" c="dimmed" truncate>
                    {t("Start")} {p.startElo} · {t("now")} {f.elo(p.elo)} · {t("since %(d)s", { d: f.date(p.entryDate) })}
                  </Text>
                </Box>
                <Group gap={6} wrap="nowrap">
                  <Tooltip label={t("Edit")}><ActionIcon size="lg" color="yellow" component={Link} href={`/elo/manage/players/${p.id}/edit/`} aria-label={t("Edit")}><IconEdit size={18} /></ActionIcon></Tooltip>
                  {p.disabled ? (
                    <Tooltip label={t("Enable")}><ActionIcon size="lg" color="green" aria-label={t("Enable")}
                      onClick={() => confirmPost({ title: p.name, body: t("Allow this player to play again?"), confirm: t("Enable"), cancel: t("Cancel"), url: `/elo/manage/players/${p.id}/toggle/`, color: "green" })}>
                      <IconPlayerPlay size={18} />
                    </ActionIcon></Tooltip>
                  ) : (
                    <Tooltip label={t("Disable")}><ActionIcon size="lg" color="red" aria-label={t("Disable")}
                      onClick={() => confirmPost({ title: p.name, body: t("Disable this player? They stay in the ranking but cannot play new matches."), confirm: t("Disable"), cancel: t("Cancel"), url: `/elo/manage/players/${p.id}/toggle/` })}>
                      <IconUserOff size={18} />
                    </ActionIcon></Tooltip>
                  )}
                </Group>
              </Group>
            ))}
          </Paper>
        ) : (
          <EmptyState>{t("No players yet – add the first one.")}</EmptyState>
        )}
      </Section>
      <SimpleGrid cols={{ base: 1, sm: 2 }} mt="lg" spacing="md">
        <Paper withBorder p="md">
          <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb="sm">{t("Exports")}</Text>
          <Group gap="xs">
            {[
              ["/elo/export/ranking.pdf", t("Ranking (PDF)")],
              ["/elo/export/ranking.csv", t("Ranking (CSV)")],
              ["/elo/export/matches.csv", t("Matches (CSV)")],
              ["/elo/export/players.csv", t("Players (CSV)")],
            ].map(([href, label]) => (
              <Button key={href} size="xs" component="a" href={href} leftSection={<IconDownload size={14} />}>{label}</Button>
            ))}
          </Group>
          <Text size="xs" c="dimmed" mt="sm">{t("Ranking exports use the current month; open the ranking for other periods.")}</Text>
        </Paper>
        <Paper withBorder p="md">
          <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb="sm">{t("Recalculate")}</Text>
          <Text size="sm" c="dimmed" mb="sm">{t("Replays the complete match history from scratch. Only needed after data repairs – entering, editing and deleting matches recalculate automatically.")}</Text>
          <Button size="xs" leftSection={<IconCalculator size={14} />}
            onClick={() => confirmPost({ title: t("Recalculate"), body: t("Recalculate the complete Elo history now?"), confirm: t("Recalculate everything"), cancel: t("Cancel"), url: "/elo/manage/recalculate/", color: "brand" })}>
            {t("Recalculate everything")}
          </Button>
        </Paper>
      </SimpleGrid>
    </>
  );
}
