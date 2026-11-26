import { Head, Link, router } from "@inertiajs/react";
import { ActionIcon, Badge, Box, Button, Group, Pagination, Paper, Select, Stack, Text, Tooltip, UnstyledButton } from "@mantine/core";
import { IconAlertTriangle, IconChevronRight, IconPlus, IconRefresh, IconSortAscending, IconSortDescending } from "@tabler/icons-react";
import dayjs from "dayjs";
import { CalendarSubscribe, type CalendarLink } from "../../components/CalendarSubscribe";
import { EmptyState, PageHeader, ReadOnlyBadge } from "../../components/ui";
import { useState } from "react";
import { useT, useTn } from "../../i18n";

interface Row {
  id: number;
  label: string;
  date: string;
  team: string;
  opponent: string;
  venue: string;
  time: string;
  location: string;
  nuliga: boolean;
  nuligaRemoved: boolean;
  nuligaManual: boolean;
  isToday: boolean;
  isPast: boolean;
  canManage: boolean;
}
interface NuligaInfo {
  syncUrl: string;
  teams: { name: string; lastSync: string | null; error: string; retrying: boolean; gaveUp: boolean }[];
}
interface Props {
  rows: Row[];
  teams: { id: number; name: string }[];
  teamId: number | null;
  allTeams: boolean;
  sort: "date" | "venue" | "opponent" | "team";
  dir: "asc" | "desc";
  page: number;
  pages: number;
  total: number;
  season: string;
  canCreate: boolean;
  nuliga: NuligaInfo | null;
  calendars: CalendarLink[];
}

/** "Sync with nuLiga" - the daily import, right now. */
function NuligaBar({ info }: { info: NuligaInfo }) {
  const t = useT();
  const [busy, setBusy] = useState(false);
  const last = info.teams.map((x) => x.lastSync).filter(Boolean).sort().pop();
  const errors = info.teams.filter((x) => x.error);
  return (
    <Paper withBorder p="sm" radius="md" mb="md">
      <Group justify="space-between" gap="sm">
        <Box style={{ minWidth: 0 }}>
          <Text size="sm" fw={700}>nuLiga</Text>
          <Text size="xs" c="dimmed">
            {last ? t("Checked daily, last time %(when)s.", { when: dayjs(last).format("DD.MM. HH:mm") }) : t("Checked daily.")}
          </Text>
          {errors.map((x) => (
            <Box key={x.name} mt={4}>
              <Badge color="red" variant="light" leftSection={<IconAlertTriangle size={12} />}>
                {x.gaveUp ? t("Sync error with nuLiga - the system admin is informed") : t("Sync error with nuLiga - next try in about 1 hour")}
              </Badge>
              <Text size="xs" c="dimmed">{x.name}: {x.error}</Text>
            </Box>
          ))}
        </Box>
        <Button
          variant="light"
          leftSection={<IconRefresh size={16} />}
          loading={busy}
          onClick={() => router.post(info.syncUrl, {}, { preserveScroll: true, onStart: () => setBusy(true), onFinish: () => setBusy(false) })}
        >
          {t("Sync with nuLiga now")}
        </Button>
      </Group>
    </Paper>
  );
}

export default function Matchdays(p: Props) {
  const t = useT();
  const tn = useTn();
  const go = (params: Record<string, string | number>) =>
    router.get(
      "/matchdays/",
      { team: p.teamId ?? "", sort: p.sort, dir: p.dir, ...params },
      { preserveState: true, preserveScroll: true, replace: true },
    );
  return (
    <>
      <Head title={t("Matchdays")} />
      <PageHeader
        title={t("Matchdays")}
        subtitle={[p.season, tn("%(n)s matchday", "%(n)s matchdays", p.total)].filter(Boolean).join(" · ")}
        actions={
          <Group gap="xs">
            <CalendarSubscribe calendars={p.calendars} />
            {p.canCreate && (
              <Button component={Link} href="/matchdays/create/" leftSection={<IconPlus size={18} />}>
                {t("New matchday")}
              </Button>
            )}
          </Group>
        }
      >
        <Group gap="sm" wrap="wrap" align="flex-end">
          <Select
            label={t("Team")}
            data={[{ value: "", label: t("All teams") }, ...p.teams.map((x) => ({ value: String(x.id), label: x.name }))]}
            value={p.teamId ? String(p.teamId) : ""}
            onChange={(v) => go({ team: v ?? "", page: 1 })}
            style={{ flex: "1 1 12rem" }}
          />
          <Select
            label={t("Sort by")}
            data={[
              { value: "date", label: t("Date") },
              { value: "opponent", label: t("Opponent") },
              { value: "venue", label: t("Venue") },
              { value: "team", label: t("Team") },
            ]}
            value={p.sort}
            onChange={(v) => go({ sort: v ?? "date" })}
            style={{ flex: "1 1 9rem" }}
          />
          <Tooltip label={p.dir === "asc" ? t("Oldest first") : t("Newest first")}>
            <ActionIcon size={36} variant="filled" color="gray" aria-label={t("Sort direction")} onClick={() => go({ dir: p.dir === "asc" ? "desc" : "asc" })}>
              {p.dir === "asc" ? <IconSortAscending size={20} /> : <IconSortDescending size={20} />}
            </ActionIcon>
          </Tooltip>
        </Group>
      </PageHeader>

      {p.nuliga && <NuligaBar info={p.nuliga} />}

      {p.rows.length === 0 ? (
        <EmptyState>{t("No matchdays yet.")}</EmptyState>
      ) : (
        <Stack gap="xs">
          {p.rows.map((m) => {
            const d = dayjs(m.date);
            return (
              <UnstyledButton key={m.id} component={Link} href={`/matchdays/${m.id}/`} className="row-link">
                <Paper withBorder p="sm" radius="md">
                  <Group wrap="nowrap" gap="md">
                    <Box ta="center" w={52} style={{ flexShrink: 0 }}>
                      <Text fw={800} fz={22} lh={1} className="num" c={m.isToday ? "teal" : undefined}>{d.format("DD")}</Text>
                      <Text size="xs" c="dimmed" tt="uppercase">{d.format("MM.YY")}</Text>
                    </Box>
                    <Box style={{ minWidth: 0, flex: 1 }}>
                      <Text fw={700} truncate>{m.opponent ? `${m.team} – ${m.opponent}` : m.label}</Text>
                      <Group gap={6} mt={4}>
                        <Badge variant="light" color="brand">{m.venue}</Badge>
                        {m.time && <Badge variant="light" color="gray">{m.time}</Badge>}
                        {m.nuligaRemoved && <Badge color="red" variant="light">{t("removed in nuLiga")}</Badge>}
                        {m.nuligaManual && <Badge color="yellow" variant="light">{t("managed by hand")}</Badge>}
                        {m.isToday && <Badge color="teal" variant="filled">{t("Today")}</Badge>}
                        {!m.isPast && !m.isToday && <Badge color="gray" variant="light">{t("upcoming")}</Badge>}
                        {!m.canManage && <ReadOnlyBadge label={t("read only")} />}
                      </Group>
                      {m.location && <Text size="xs" c="dimmed" truncate mt={4}>{m.location}</Text>}
                    </Box>
                    <IconChevronRight size={18} style={{ opacity: 0.5, flexShrink: 0 }} />
                  </Group>
                </Paper>
              </UnstyledButton>
            );
          })}
        </Stack>
      )}
      {p.pages > 1 && (
        <Group justify="center" mt="lg">
          <Pagination total={p.pages} value={p.page} onChange={(n) => go({ page: n })} />
        </Group>
      )}
    </>
  );
}
