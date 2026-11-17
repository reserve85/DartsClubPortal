import { Head, Link, router } from "@inertiajs/react";
import { Affix, Alert, Avatar, Badge, Box, Button, Checkbox, Group, Pagination, Paper, ScrollArea, SimpleGrid, Table, Text, Tooltip, Transition } from "@mantine/core";
import { IconCash, IconDeviceFloppy, IconEdit, IconInfoCircle, IconLock, IconPlus, IconUserPlus, IconUsers } from "@tabler/icons-react";
import { modals } from "@mantine/modals";
import { useMemo, useState } from "react";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { EmptyState, PageHeader, Section } from "../../components/ui";
import { useT, useTn } from "../../i18n";
import { colorFor } from "../../theme";

interface TeamRow {
  id: number;
  name: string;
  activeInSeason: boolean;
  captains: number;
  players: number;
  financeUrl: string;
  editUrl: string | null;
}
interface Column {
  id: number;
  name: string;
  editable: boolean;
}
interface PlayerRow {
  id: number;
  name: string;
  active: boolean;
  avatar: string;
  assigned: number[];
  canEdit: boolean;
}
interface Props {
  season: string;
  seasonScoped: boolean;
  isAdmin: boolean;
  teams: TeamRow[];
  columns: Column[];
  players: PlayerRow[];
  page: number;
  pages: number;
  total: number;
}

const key = (p: number, t: number) => `${p}:${t}`;

export default function Teams(p: Props) {
  const t = useT();
  const tn = useTn();
  const initial = useMemo(() => new Set(p.players.flatMap((pl) => pl.assigned.map((tid) => key(pl.id, tid)))), [p.players]);
  const [checked, setChecked] = useState<Set<string>>(initial);
  const [busy, setBusy] = useState(false);
  const dirty = checked.size !== initial.size || [...checked].some((k) => !initial.has(k));
  const anyEditable = p.columns.some((c) => c.editable);
  const toggle = (k: string) =>
    setChecked((cur) => {
      const next = new Set(cur);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  const save = () =>
    router.post(
      "/teams/",
      { players: p.players.map((pl) => pl.id), assign: [...checked] },
      { preserveScroll: true, onStart: () => setBusy(true), onFinish: () => setBusy(false) },
    );

  return (
    <>
      <Head title={t("Teams & players")} />
      <PageHeader
        title={t("Teams & players")}
        subtitle={p.season ? `${t("Season")} ${p.season}` : undefined}
        left={<IconUsers size={40} stroke={1.5} />}
        actions={
          <>
            {p.isAdmin && (
              <Button component={Link} href="/teams/create/" leftSection={<IconPlus size={18} />}>{t("New team")}</Button>
            )}
            <Button component={Link} href="/players/create/" leftSection={<IconUserPlus size={18} />}>{t("New player")}</Button>
          </>
        }
      />

      <Section title={t("Teams")}>
        {p.seasonScoped && (
          <Text size="sm" c="dimmed" mb="xs">{t("Only teams active in this season appear in the assignment below.")}</Text>
        )}
        {p.teams.length === 0 ? (
          <EmptyState>{t("No teams yet.")}</EmptyState>
        ) : (
          <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="sm">
            {p.teams.map((team) => (
              <Paper key={team.id} withBorder p="sm" radius="md" style={{ opacity: team.activeInSeason ? 1 : 0.7 }}>
                <Group justify="space-between" wrap="nowrap" gap="sm">
                  <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
                    <Avatar color={colorFor(team.name)} variant="filled" radius="xl">{team.name.slice(0, 2).toUpperCase()}</Avatar>
                    <Box style={{ minWidth: 0 }}>
                      <Text fw={800} truncate>{team.name}</Text>
                      <Text size="xs" c="dimmed">
                        {tn("%(n)s player", "%(n)s players", team.players)} · {tn("%(n)s captain", "%(n)s captains", team.captains)}
                      </Text>
                    </Box>
                  </Group>
                  <Badge color={team.activeInSeason ? "teal" : "gray"} variant="light" style={{ flexShrink: 0 }}>
                    {team.activeInSeason ? t("active") : t("inactive")}
                  </Badge>
                </Group>
                <Group gap="xs" mt="sm">
                  <Button size="compact-sm" component={Link} href={team.financeUrl} leftSection={<IconCash size={14} />}>{t("Finances")}</Button>
                  {team.editUrl && (
                    <Button size="compact-sm" color="yellow" component={Link} href={team.editUrl} leftSection={<IconEdit size={14} />}>{t("Edit")}</Button>
                  )}
                </Group>
              </Paper>
            ))}
          </SimpleGrid>
        )}
      </Section>

      <Section
        title={`${t("Team assignment")} (${p.total})`}
        right={
          anyEditable && (
            <Button leftSection={<IconDeviceFloppy size={18} />} disabled={!dirty} loading={busy} onClick={save}>
              {t("Save assignments")}
            </Button>
          )
        }
      >
        {!anyEditable && p.columns.length > 0 && (
          <Alert color="gray" icon={<IconInfoCircle />} mb="sm">{t("You can only view the assignment of these teams.")}</Alert>
        )}
        {p.players.length === 0 ? (
          <EmptyState>{t("No players yet.")}</EmptyState>
        ) : (
          <Paper withBorder radius="md">
            <ScrollArea type="auto">
              <Table verticalSpacing={6} highlightOnHover miw={260 + p.columns.length * 90}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th style={{ position: "sticky", left: 0, background: "var(--mantine-color-body)", zIndex: 1 }}>{t("Player")}</Table.Th>
                    {p.columns.map((c) => (
                      <Table.Th key={c.id} ta="center" style={{ whiteSpace: "nowrap" }}>
                        {c.name} {!c.editable && <IconLock size={12} style={{ verticalAlign: -1, opacity: 0.6 }} />}
                      </Table.Th>
                    ))}
                    <Table.Th />
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {p.players.map((pl) => (
                    <Table.Tr key={pl.id}>
                      <Table.Td style={{ position: "sticky", left: 0, background: "var(--mantine-color-body)", zIndex: 1 }}>
                        <Group gap="xs" wrap="nowrap">
                          <PlayerAvatar name={pl.name} src={pl.avatar} size={28} muted={!pl.active} />
                          <Text component={Link} href={`/players/${pl.id}/`} size="sm" fw={600} c={pl.active ? undefined : "dimmed"} td={pl.active ? undefined : "line-through"} title={pl.active ? undefined : t("inactive")} style={{ whiteSpace: "nowrap" }}>
                            {pl.name}
                          </Text>
                        </Group>
                      </Table.Td>
                      {p.columns.map((c) => {
                        const k = key(pl.id, c.id);
                        return (
                          <Table.Td key={c.id} ta="center">
                            <Tooltip label={t("Only your own team can be changed.")} disabled={c.editable}>
                              <Checkbox
                                display="inline-block"
                                color="teal"
                                size="md"
                                checked={checked.has(k)}
                                disabled={!c.editable}
                                onChange={() => toggle(k)}
                                aria-label={`${pl.name} – ${c.name}`}
                              />
                            </Tooltip>
                          </Table.Td>
                        );
                      })}
                      <Table.Td ta="right">
                        {pl.canEdit && (
                          <Button size="compact-xs" color="yellow" component={Link} href={`/players/${pl.id}/edit/`}>{t("Edit")}</Button>
                        )}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </ScrollArea>
          </Paper>
        )}
        {p.pages > 1 && (
          <Group justify="center" mt="md">
            <Pagination
              total={p.pages}
              value={p.page}
              onChange={(n) => {
                const go = () => router.get("/teams/", { page: n }, { preserveScroll: true });
                if (!dirty) return go();
                modals.openConfirmModal({
                  modalId: "confirm", // one at a time: a double tap must not stack a second dialog
                  title: t("Unsaved changes"),
                  children: <Text size="sm">{t("Discard the unsaved assignment changes?")}</Text>,
                  labels: { confirm: t("Discard"), cancel: t("Cancel") },
                  confirmProps: { color: "red" },
                  cancelProps: { variant: "filled", color: "gray" },
                  onConfirm: go,
                });
              }}
            />
          </Group>
        )}
      </Section>

      {/* Floating save bar while there are unsaved assignment changes. */}
      <Affix position={{ bottom: 16, left: 16, right: 16 }} zIndex={350}>
        <Transition transition="slide-up" mounted={dirty}>
          {(styles) => (
            <Paper style={{ ...styles, maxWidth: 520, margin: "0 auto" }} withBorder shadow="xl" p="sm" radius="md">
              <Group justify="space-between" wrap="nowrap" gap="sm">
                <Text size="sm" fw={600}>{t("Unsaved changes")}</Text>
                <Group gap="xs" wrap="nowrap">
                  <Button color="gray" onClick={() => setChecked(new Set(initial))}>{t("Discard")}</Button>
                  <Button leftSection={<IconDeviceFloppy size={18} />} loading={busy} onClick={save}>{t("Save")}</Button>
                </Group>
              </Group>
            </Paper>
          )}
        </Transition>
      </Affix>
    </>
  );
}
