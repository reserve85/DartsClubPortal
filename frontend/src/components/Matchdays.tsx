import { Link, router } from "@inertiajs/react";
import { Badge, Box, Button, Group, Paper, Text, UnstyledButton } from "@mantine/core";
import { IconAlertTriangle, IconChevronRight, IconRefresh } from "@tabler/icons-react";
import dayjs from "dayjs";
import { useState } from "react";
import { useT } from "../i18n";

/** One matchday as the schedule, the overview and the matchday list show it. */
export interface MatchdayRowData {
  id: number;
  date: string;
  time: string;
  teamId: number;
  team: string;
  opponent: string;
  venue: string;
  home: boolean;
  location: string;
  removed: boolean;
  manual?: boolean;
  isToday: boolean;
  isPast: boolean;
  url: string | null;
}

/** Date block, "Team – opponent", home/away, time, venue; own team and today stand out. */
export function MatchdayRow({ row, own }: { row: MatchdayRowData; own: boolean }) {
  const t = useT();
  const highlight = row.isToday
    ? { background: "var(--mantine-color-teal-light)", boxShadow: "inset 3px 0 0 var(--mantine-color-teal-6)" }
    : own
      ? { background: "var(--mantine-color-brand-light)", boxShadow: "inset 3px 0 0 var(--mantine-color-brand-6)" }
      : undefined;
  const body = (
    <Paper withBorder p="sm" radius="md" style={{ ...highlight, opacity: row.isPast ? 0.7 : 1 }}>
      <Group wrap="nowrap" gap="md">
        <Box ta="center" w={52} style={{ flexShrink: 0 }}>
          <Text fw={800} fz={22} lh={1} className="num" c={row.isToday ? "teal" : undefined}>{dayjs(row.date).format("DD")}</Text>
          <Text size="xs" c="dimmed" tt="uppercase">{dayjs(row.date).format("dd MM")}</Text>
        </Box>
        <Box style={{ minWidth: 0, flex: 1 }}>
          <Text fw={700} truncate td={row.removed ? "line-through" : undefined}>{row.team} – {row.opponent}</Text>
          <Group gap={6} mt={4}>
            {row.isToday && <Badge color="teal" variant="filled">{t("Today")}</Badge>}
            <Badge variant="light" color="brand">{row.venue}</Badge>
            {row.time && <Badge variant="light" color="gray">{row.time}</Badge>}
            {own && <Badge variant="light" color="brand">{t("my team")}</Badge>}
            {row.manual && <Badge color="yellow" variant="light">{t("managed by hand")}</Badge>}
            {row.removed && <Badge color="red" variant="light">{t("removed in nuLiga")}</Badge>}
          </Group>
          {row.location && <Text size="xs" c="dimmed" truncate mt={4}>{row.location}</Text>}
        </Box>
        {row.url && <IconChevronRight size={18} style={{ opacity: 0.5, flexShrink: 0 }} />}
      </Group>
    </Paper>
  );
  return row.url ? (
    <UnstyledButton component={Link} href={row.url} className="row-link" display="block">{body}</UnstyledButton>
  ) : (
    body
  );
}

export interface NuligaInfo {
  syncUrl: string;
  teams: { name: string; lastSync: string | null; error: string; retrying: boolean; gaveUp: boolean }[];
}

/** "Sync with nuLiga now" plus the state of the daily import. */
export function NuligaBar({ info }: { info: NuligaInfo }) {
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
