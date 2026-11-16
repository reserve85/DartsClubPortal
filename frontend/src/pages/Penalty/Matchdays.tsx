import { Head, Link, router } from "@inertiajs/react";
import { ActionIcon, Badge, Box, Button, Group, Pagination, Paper, Select, Stack, Text, Tooltip, UnstyledButton } from "@mantine/core";
import { IconChevronRight, IconPlus, IconSortAscending, IconSortDescending } from "@tabler/icons-react";
import dayjs from "dayjs";
import { EmptyState, PageHeader, ReadOnlyBadge } from "../../components/ui";
import { useT, useTn } from "../../i18n";

interface Row {
  id: number;
  label: string;
  date: string;
  team: string;
  opponent: string;
  venue: string;
  isToday: boolean;
  isPast: boolean;
  canManage: boolean;
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
          p.canCreate && (
            <Button component={Link} href="/matchdays/create/" leftSection={<IconPlus size={18} />}>
              {t("New matchday")}
            </Button>
          )
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
                        {m.isToday && <Badge color="teal" variant="filled">{t("Today")}</Badge>}
                        {!m.isPast && !m.isToday && <Badge color="gray" variant="light">{t("upcoming")}</Badge>}
                        {!m.canManage && <ReadOnlyBadge label={t("read only")} />}
                      </Group>
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
