import { Head, Link, router } from "@inertiajs/react";
import { Box, Button, Group, SegmentedControl, Select, Stack, Text } from "@mantine/core";
import { IconCalendarEvent, IconPlus } from "@tabler/icons-react";
import dayjs from "dayjs";
import { useState } from "react";
import { CalendarSubscribe, type CalendarLink } from "../components/CalendarSubscribe";
import { MatchdayRow, NuligaBar, type MatchdayRowData, type NuligaInfo } from "../components/Matchdays";
import { EmptyState, PageHeader } from "../components/ui";
import { useT, useTn } from "../i18n";

interface Props {
  season: string;
  showPast: boolean;
  teamId: number | null;
  teams: { id: number; name: string; own: boolean }[];
  rows: MatchdayRowData[];
  calendars: CalendarLink[];
  /** Admins and captains: new matchday, nuLiga sync. */
  canCreate: boolean;
  nuliga: NuligaInfo | null;
}

/** The schedule of every team - for everybody; admins and captains manage it here too. */
export default function Schedule({ season, showPast, teamId, teams, rows, calendars, canCreate, nuliga }: Props) {
  const t = useT();
  const tn = useTn();
  const [team, setTeam] = useState<string>(teamId ? String(teamId) : "");
  const own = new Set(teams.filter((x) => x.own).map((x) => x.id));
  const shown = rows.filter((r) => !team || String(r.teamId) === team);
  // One block per month.
  const months: { key: string; label: string; rows: MatchdayRowData[] }[] = [];
  for (const r of shown) {
    const key = r.date.slice(0, 7);
    let block = months.find((m) => m.key === key);
    if (!block) {
      block = { key, label: dayjs(r.date).format("MMMM YYYY"), rows: [] };
      months.push(block);
    }
    block.rows.push(r);
  }

  return (
    <>
      <Head title={t("Schedule")} />
      <PageHeader
        title={t("Schedule")}
        subtitle={[season, tn("%(n)s matchday", "%(n)s matchdays", shown.length)].filter(Boolean).join(" · ")}
        left={<IconCalendarEvent size={40} stroke={1.5} />}
        actions={
          <Group gap="xs">
            <CalendarSubscribe calendars={calendars} />
            {canCreate && (
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
            data={[{ value: "", label: t("All teams") }, ...teams.map((x) => ({ value: String(x.id), label: x.own ? `${x.name} ★` : x.name }))]}
            value={team}
            onChange={(v) => setTeam(v ?? "")}
            w={260}
          />
          <SegmentedControl
            value={showPast ? "all" : "upcoming"}
            onChange={(v) => router.get("/schedule/", { ...(v === "all" ? { past: "1" } : {}), ...(team ? { team } : {}) }, { preserveScroll: true, preserveState: true, replace: true })}
            data={[
              { value: "upcoming", label: t("Upcoming") },
              { value: "all", label: t("Whole season") },
            ]}
          />
        </Group>
      </PageHeader>

      {nuliga && <NuligaBar info={nuliga} />}

      {months.length === 0 ? (
        <EmptyState>{t("No matchdays yet.")}</EmptyState>
      ) : (
        <Stack gap="lg">
          {months.map((m) => (
            <Box key={m.key}>
              <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb={6}>{m.label}</Text>
              <Stack gap="xs">
                {m.rows.map((r) => (
                  <MatchdayRow key={r.id} row={r} own={own.has(r.teamId)} />
                ))}
              </Stack>
            </Box>
          ))}
        </Stack>
      )}
    </>
  );
}
