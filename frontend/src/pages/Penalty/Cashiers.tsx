import { Head, router } from "@inertiajs/react";
import { Avatar, Badge, Box, Button, Group, Paper, Select, SimpleGrid, Text, Timeline } from "@mantine/core";
import { IconCash, IconCrown } from "@tabler/icons-react";
import { useState } from "react";
import { PageHeader, ReadOnlyBadge, Section } from "../../components/ui";
import { useFormat, useT } from "../../i18n";
import { colorFor } from "../../theme";

interface History {
  name: string;
  from: string | null;
  to: string | null;
  by: string;
  open: boolean;
}
interface Team {
  id: number;
  name: string;
  canEdit: boolean;
  cashier: { id: number; name: string; isCaptain: boolean } | null;
  history: History[];
}
interface Props {
  teams: Team[];
  candidates: { value: string; label: string }[];
  isAdmin: boolean;
}

function TeamCard({ team, candidates }: { team: Team; candidates: Props["candidates"] }) {
  const t = useT();
  const f = useFormat();
  const current = team.cashier ? String(team.cashier.id) : "";
  const [pick, setPick] = useState<string>(current);
  const [busy, setBusy] = useState(false);
  const save = () =>
    router.post("/teams/cashier/set/", { team: team.id, user: pick }, {
      preserveScroll: true,
      onStart: () => setBusy(true),
      onFinish: () => setBusy(false),
    });
  return (
    <Paper withBorder p="md" radius="md">
      <Group justify="space-between" wrap="nowrap" mb="sm">
        <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
          <Avatar color={colorFor(team.name)} variant="filled" radius="xl">{team.name.slice(0, 2).toUpperCase()}</Avatar>
          <Text fw={800} truncate>{team.name}</Text>
        </Group>
        {!team.canEdit && <ReadOnlyBadge label={t("read only")} />}
      </Group>

      <Group gap={8} mb="sm">
        <IconCash size={18} color="var(--mantine-color-teal-filled)" />
        {team.cashier ? (
          <>
            <Text fw={700}>{team.cashier.name}</Text>
            {team.cashier.isCaptain && (
              <Badge size="sm" color="yellow" variant="light" leftSection={<IconCrown size={12} />}>{t("Captain")}</Badge>
            )}
          </>
        ) : (
          <Text c="dimmed">{t("No cashier yet — nobody can record payments.")}</Text>
        )}
      </Group>

      {team.canEdit && (
        <Group gap="xs" align="flex-end" wrap="nowrap">
          <Select
            style={{ flex: 1 }}
            label={t("Cashier")}
            data={[{ value: "", label: t("— no cashier —") }, ...candidates]}
            value={pick}
            onChange={(v) => setPick(v ?? "")}
            searchable={candidates.length > 8}
            allowDeselect={false}
          />
          <Button onClick={save} loading={busy} disabled={pick === current}>{t("Save")}</Button>
        </Group>
      )}

      {team.history.length > 0 && (
        <Box mt="md">
          <Text size="xs" tt="uppercase" fw={700} c="dimmed" mb={6}>{t("History")}</Text>
          <Timeline bulletSize={14} lineWidth={2} active={0}>
            {team.history.map((h, i) => (
              <Timeline.Item key={i} color={h.open ? "teal" : "gray"} title={<Text size="sm" fw={h.open ? 700 : 500}>{h.name || "—"}</Text>}>
                <Text size="xs" c="dimmed">
                  {h.from ? f.date(h.from) : ""} – {h.to ? f.date(h.to) : t("today")}
                  {h.by ? ` · ${t("set by %(name)s", { name: h.by })}` : ""}
                </Text>
              </Timeline.Item>
            ))}
          </Timeline>
        </Box>
      )}
    </Paper>
  );
}

export default function Cashiers({ teams, candidates }: Props) {
  const t = useT();
  return (
    <>
      <Head title={t("Cash box")} />
      <PageHeader
        title={t("Cash box")}
        subtitle={t("Only the cashier of a team records payments and payouts. Everyone else sees the balances read-only.")}
        left={<IconCash size={40} stroke={1.5} />}
      />
      <Section title={t("Cashier per team")}>
        <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
          {teams.map((team) => (
            <TeamCard key={team.id} team={team} candidates={candidates} />
          ))}
        </SimpleGrid>
      </Section>
    </>
  );
}
