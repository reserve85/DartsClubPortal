import { Head, Link, router } from "@inertiajs/react";
import { Badge, Box, Group, Paper, SegmentedControl, Select, Stack, Text, UnstyledButton } from "@mantine/core";
import { IconCalendarEvent, IconChevronRight } from "@tabler/icons-react";
import dayjs from "dayjs";
import { useState } from "react";
import { CalendarSubscribe, type CalendarLink } from "../components/CalendarSubscribe";
import { EmptyState, PageHeader } from "../components/ui";
import { useFormat, useT } from "../i18n";

interface Row {
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
  isToday: boolean;
  isPast: boolean;
  url: string | null;
}

interface Props {
  season: string;
  showPast: boolean;
  teams: { id: number; name: string; own: boolean }[];
  rows: Row[];
  calendars: CalendarLink[];
}

/** Schedule of every team: read-only for every account, own teams highlighted. */
export default function Schedule({ season, showPast, teams, rows, calendars }: Props) {
  const t = useT();
  const f = useFormat();
  const [team, setTeam] = useState<string>("");
  const own = new Set(teams.filter((x) => x.own).map((x) => x.id));
  const shown = rows.filter((r) => !team || String(r.teamId) === team);
  // One block per month.
  const months: { key: string; label: string; rows: Row[] }[] = [];
  for (const r of shown) {
    const key = r.date.slice(0, 7);
    let block = months.find((m) => m.key === key);
    if (!block) {
      block = { key, label: dayjs(r.date).format("MMMM YYYY"), rows: [] };
      months.push(block);
    }
    block.rows.push(r);
  }

  const line = (r: Row) => {
    const mine = own.has(r.teamId);
    const body = (
      <Paper
        withBorder
        p="sm"
        radius="md"
        style={mine ? { background: "var(--mantine-color-brand-light)", boxShadow: "inset 3px 0 0 var(--mantine-color-brand-6)" } : undefined}
      >
        <Group wrap="nowrap" gap="md">
          <Box ta="center" w={52} style={{ flexShrink: 0 }}>
            <Text fw={800} fz={22} lh={1} className="num" c={r.isToday ? "teal" : r.isPast ? "dimmed" : undefined}>{dayjs(r.date).format("DD")}</Text>
            <Text size="xs" c="dimmed" tt="uppercase">{dayjs(r.date).format("dd")}</Text>
          </Box>
          <Box style={{ minWidth: 0, flex: 1 }}>
            <Text fw={700} truncate td={r.removed ? "line-through" : undefined}>{r.team} – {r.opponent}</Text>
            <Group gap={6} mt={4}>
              <Badge variant="light" color="brand">{r.venue}</Badge>
              {r.time && <Badge variant="light" color="gray">{r.time}</Badge>}
              {r.isToday && <Badge color="teal" variant="filled">{t("Today")}</Badge>}
              {r.removed && <Badge color="red" variant="light">{t("removed in nuLiga")}</Badge>}
            </Group>
            {r.location && <Text size="xs" c="dimmed" truncate mt={4}>{r.location}</Text>}
          </Box>
          {r.url && <IconChevronRight size={18} style={{ opacity: 0.5, flexShrink: 0 }} />}
        </Group>
      </Paper>
    );
    return r.url ? (
      <UnstyledButton key={r.id} component={Link} href={r.url} className="row-link">{body}</UnstyledButton>
    ) : (
      <Box key={r.id}>{body}</Box>
    );
  };

  return (
    <>
      <Head title={t("Schedule")} />
      <PageHeader
        title={t("Schedule")}
        subtitle={[season, t("all teams")].filter(Boolean).join(" · ")}
        left={<IconCalendarEvent size={40} stroke={1.5} />}
        actions={<CalendarSubscribe calendars={calendars} />}
      >
        <Group gap="sm" wrap="wrap" align="flex-end">
          <Select
            label={t("Team")}
            data={[{ value: "", label: t("All teams") }, ...teams.map((x) => ({ value: String(x.id), label: x.own ? `${x.name} ★` : x.name }))]}
            value={team}
            onChange={(v) => setTeam(v ?? "")}
            w={260}
          />
          <SegmentedControl
            value={showPast ? "all" : "upcoming"}
            onChange={(v) => router.get("/schedule/", v === "all" ? { past: "1" } : {}, { preserveScroll: true, preserveState: true, replace: true })}
            data={[
              { value: "upcoming", label: t("Upcoming") },
              { value: "all", label: t("Whole season") },
            ]}
          />
        </Group>
      </PageHeader>

      {months.length === 0 ? (
        <EmptyState>{t("No matchdays yet.")}</EmptyState>
      ) : (
        <Stack gap="lg">
          {months.map((m) => (
            <Box key={m.key}>
              <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb={6}>{m.label}</Text>
              <Stack gap="xs">{m.rows.map(line)}</Stack>
            </Box>
          ))}
        </Stack>
      )}
      <Text size="xs" c="dimmed" mt="md">{t("%(n)s matchdays", { n: f.number(shown.length) })}</Text>
    </>
  );
}
