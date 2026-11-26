import { Head, Link, router } from "@inertiajs/react";
import { Alert, Avatar, Badge, Box, Button, Checkbox, Group, Modal, Paper, ScrollArea, SimpleGrid, Stack, Text, UnstyledButton } from "@mantine/core";
import { IconAlertTriangle, IconEdit, IconPlus, IconUsers } from "@tabler/icons-react";
import { useState } from "react";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { EmptyState, PageHeader, ReadOnlyBadge, Section, StatGrid, StatTile } from "../../components/ui";
import { useFormat, useT } from "../../i18n";
import { colorFor } from "../../theme";

interface Person {
  id: number;
  name: string;
  avatar: string;
}
interface PenaltyRow {
  id: number;
  when: string;
  player: string;
  playerAvatar: string;
  description: string;
  amount: number;
  group: boolean;
  manual: boolean;
}
interface Props {
  matchday: {
    id: number;
    label: string;
    date: string;
    team: string;
    season: string;
    opponent: string;
    venue: string;
    time: string;
    location: string;
    nuligaRemoved: boolean;
    nuligaManual: boolean;
    description: string;
    isToday: boolean;
  };
  canManage: boolean;
  participants: Person[];
  eligible: Person[];
  penalties: PenaltyRow[];
  total: number;
}

function ParticipantEditor({ opened, onClose, eligible, selected, url }: { opened: boolean; onClose: () => void; eligible: Person[]; selected: number[]; url: string }) {
  const t = useT();
  const [ids, setIds] = useState<number[]>(selected);
  const [busy, setBusy] = useState(false);
  const toggle = (id: number) => setIds((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  return (
    <Modal opened={opened} onClose={onClose} title={<Text fw={800}>{t("Participants")}</Text>} size="md">
      <Stack>
        <Group justify="space-between">
          <Text size="sm" c="dimmed">{t("%(n)s selected", { n: ids.length })}</Text>
          <Group gap="xs">
            <Button size="xs" color="gray" onClick={() => setIds(eligible.map((e) => e.id))}>{t("All")}</Button>
            <Button size="xs" color="gray" onClick={() => setIds([])}>{t("None")}</Button>
          </Group>
        </Group>
        {eligible.length === 0 ? (
          <Alert color="yellow">{t("No active players in this team for the season.")}</Alert>
        ) : (
          <ScrollArea.Autosize mah="55vh" type="auto">
            <SimpleGrid cols={{ base: 1, xs: 2 }} spacing={6}>
              {eligible.map((e) => {
                const on = ids.includes(e.id);
                return (
                  <UnstyledButton key={e.id} onClick={() => toggle(e.id)} aria-pressed={on}>
                    <Paper withBorder p="xs" radius="md" bg={on ? "var(--mantine-color-teal-light)" : undefined} style={{ borderColor: on ? "var(--mantine-color-teal-filled)" : undefined }}>
                      <Group gap="sm" wrap="nowrap">
                        <Checkbox checked={on} readOnly tabIndex={-1} color="teal" />
                        <PlayerAvatar name={e.name} src={e.avatar} size={28} />
                        <Text size="sm" fw={600} truncate>{e.name}</Text>
                      </Group>
                    </Paper>
                  </UnstyledButton>
                );
              })}
            </SimpleGrid>
          </ScrollArea.Autosize>
        )}
        <Group justify="flex-end">
          <Button color="gray" onClick={onClose}>{t("Cancel")}</Button>
          <Button
            disabled={ids.length === 0}
            loading={busy}
            onClick={() =>
              router.post(url, { participants: ids }, {
                preserveScroll: true,
                onStart: () => setBusy(true),
                onFinish: () => setBusy(false),
                onSuccess: onClose,
              })
            }
          >
            {t("Save participants")}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export default function MatchdayDetail({ matchday: m, canManage, participants, eligible, penalties, total }: Props) {
  const t = useT();
  const f = useFormat();
  const [editing, setEditing] = useState(false);
  return (
    <>
      <Head title={m.label} />
      <PageHeader
        title={m.opponent ? `${m.team} – ${m.opponent}` : m.label}
        subtitle={[f.date(m.date), m.time, m.venue, m.location, m.season, m.nuligaManual ? t("managed by hand") : ""].filter(Boolean).join(" · ")}
        left={<Avatar color={colorFor(m.team)} variant="filled" radius="xl" size={52}>{m.team.slice(0, 2).toUpperCase()}</Avatar>}
        actions={
          canManage ? (
            <>
              <Button component={Link} href={`/matchdays/${m.id}/penalties/add/`} leftSection={<IconPlus size={18} />}>{t("Add penalty")}</Button>
              <Button color="yellow" component={Link} href={`/matchdays/${m.id}/edit/`} leftSection={<IconEdit size={18} />}>{t("Edit")}</Button>
            </>
          ) : (
            <ReadOnlyBadge label={t("read only")} />
          )
        }
      >
        {m.isToday && <Badge color="teal" variant="filled" mb={m.description ? "xs" : 0}>{t("Today")}</Badge>}
        {m.description && <Text size="sm">{m.description}</Text>}
      </PageHeader>
      {m.nuligaRemoved && (
        <Alert color="red" variant="light" icon={<IconAlertTriangle />} mb="md">
          {t("This matchday is no longer in the nuLiga schedule. If it was cancelled, delete it (edit page).")}
        </Alert>
      )}

      <StatGrid>
        <StatTile label={t("Participants")} value={participants.length} />
        <StatTile label={t("Penalties")} value={penalties.length} />
        <StatTile label={t("Total")} value={f.euro(total)} color={total > 0 ? "red" : undefined} />
      </StatGrid>

      <Section
        title={t("Participants")}
        right={canManage && (
          <Button size="sm" leftSection={<IconUsers size={16} />} onClick={() => setEditing(true)}>
            {participants.length ? t("Edit participants") : t("Add players")}
          </Button>
        )}
      >
        {participants.length === 0 ? (
          <Text c="dimmed" size="sm">{t("No participants.")}</Text>
        ) : (
          <Group gap={8}>
            {participants.map((p) => (
              <Badge key={p.id} size="lg" variant="default" radius="xl" pl={4} leftSection={<PlayerAvatar name={p.name} src={p.avatar} size={22} />} style={{ textTransform: "none" }}>
                {p.name}
              </Badge>
            ))}
          </Group>
        )}
      </Section>

      <Section title={t("Penalties")}>
        {penalties.length === 0 ? (
          <EmptyState>{t("No penalties yet.")}</EmptyState>
        ) : (
          <Stack gap="xs">
            {penalties.map((p) => (
              <Paper key={p.id} withBorder p="sm" radius="md">
                <Group wrap="nowrap" gap="sm" align="center">
                  <PlayerAvatar name={p.player} src={p.playerAvatar} size={36} />
                  <Box style={{ minWidth: 0, flex: 1 }}>
                    <Group gap={6} wrap="nowrap">
                      <Text fw={700} truncate>{p.player}</Text>
                      {p.group && <Badge size="xs" color="gray" variant="light">{t("group")}</Badge>}
                      {p.manual && <Badge size="xs" color="yellow" variant="light">{t("manual")}</Badge>}
                    </Group>
                    <Text size="sm" c="dimmed" lineClamp={2}>{p.description}</Text>
                  </Box>
                  <Stack gap={4} align="flex-end" style={{ flexShrink: 0 }}>
                    <Text fw={800} c="red" className="num">{f.euro(p.amount)}</Text>
                    {canManage && (
                      <Button size="compact-xs" color="yellow" component={Link} href={`/penalties/${p.id}/edit/`}>{t("Edit")}</Button>
                    )}
                  </Stack>
                </Group>
              </Paper>
            ))}
          </Stack>
        )}
      </Section>

      {canManage && editing && (
        <ParticipantEditor
          opened={editing}
          onClose={() => setEditing(false)}
          eligible={eligible}
          selected={participants.map((p) => p.id)}
          url={`/matchdays/${m.id}/participants/`}
        />
      )}
    </>
  );
}
