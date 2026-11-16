import { Head, Link } from "@inertiajs/react";
import { Badge, Box, Button, Group, Paper, SimpleGrid, Stack, Text, UnstyledButton } from "@mantine/core";
import { IconCash, IconChevronRight, IconEdit } from "@tabler/icons-react";
import { AvatarUpload } from "../../components/AvatarUpload";
import { BalanceTiles } from "../../components/BalanceTiles";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { EmptyState, PageHeader, Section } from "../../components/ui";
import { useFormat, useT } from "../../i18n";

interface TeamRow {
  id: number;
  name: string;
  total: number;
  paid: number;
  balance: number;
  financeUrl: string;
}
interface PenaltyRow {
  id: number;
  when: string;
  matchday: string;
  matchdayId: number;
  description: string;
  amount: number;
}
interface Props {
  player: { id: number; name: string; active: boolean; avatar: string };
  season: string;
  canEdit: boolean;
  totals: { total: number; paid: number; balance: number };
  teams: TeamRow[];
  penalties: PenaltyRow[];
}

export default function PlayerDetail({ player, season, canEdit, totals, teams, penalties }: Props) {
  const t = useT();
  const f = useFormat();
  return (
    <>
      <Head title={player.name} />
      <PageHeader
        title={player.name}
        subtitle={[season && `${t("Season")} ${season}`, teams.map((x) => x.name).join(", ")].filter(Boolean).join(" · ")}
        left={<PlayerAvatar name={player.name} src={player.avatar} size={56} muted={!player.active} />}
        actions={
          <>
            {!player.active && <Badge color="gray" variant="light" size="lg">{t("inactive")}</Badge>}
            {canEdit && (
              <Button color="yellow" component={Link} href={`/players/${player.id}/edit/`} leftSection={<IconEdit size={18} />}>
                {t("Edit")}
              </Button>
            )}
          </>
        }
      />

      <BalanceTiles {...totals} />

      {teams.length > 0 && (
        <Section title={t("Per team")}>
          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
            {teams.map((team) => (
              <Paper key={team.id} withBorder p="sm" radius="md">
                <Group justify="space-between">
                  <Text fw={800}>{team.name}</Text>
                  <Text fw={800} c={team.balance > 0 ? "red" : "teal"} className="num">
                    {team.balance < 0 ? `${t("Credit")} ${f.euro(-team.balance)}` : f.euro(team.balance)}
                  </Text>
                </Group>
                <Group justify="space-between" mt={4} wrap="nowrap" gap="xs">
                  <Text size="xs" c="dimmed">
                    {t("Penalties total")} {f.euro(team.total)} · {t("Penalties settled")} {f.euro(team.paid)}
                  </Text>
                  <Button size="compact-xs" component={Link} href={team.financeUrl} leftSection={<IconCash size={12} />} style={{ flexShrink: 0 }}>
                    {t("Finances")}
                  </Button>
                </Group>
              </Paper>
            ))}
          </SimpleGrid>
        </Section>
      )}

      <Section title={t("Penalties")}>
        {penalties.length === 0 ? (
          <EmptyState>{t("No penalties yet.")}</EmptyState>
        ) : (
          <Stack gap="xs">
            {penalties.map((p) => (
              <UnstyledButton key={p.id} component={Link} href={`/matchdays/${p.matchdayId}/`} className="row-link">
                <Paper withBorder p="sm" radius="md">
                  <Group wrap="nowrap" gap="sm">
                    <Box style={{ minWidth: 0, flex: 1 }}>
                      <Text fw={700} size="sm" lineClamp={2}>{p.description}</Text>
                      <Text size="xs" c="dimmed" truncate>{p.matchday}</Text>
                    </Box>
                    <Text fw={800} c="red" className="num" style={{ flexShrink: 0 }}>{f.euro(p.amount)}</Text>
                    <IconChevronRight size={16} style={{ opacity: 0.5, flexShrink: 0 }} />
                  </Group>
                </Paper>
              </UnstyledButton>
            ))}
          </Stack>
        )}
      </Section>

      {canEdit && <AvatarUpload playerId={player.id} name={player.name} avatar={player.avatar} />}
    </>
  );
}
