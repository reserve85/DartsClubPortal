import { Head, Link } from "@inertiajs/react";
import { Badge, Box, Button, Group, Paper, SegmentedControl, Stack, Text, TextInput } from "@mantine/core";
import { IconEdit, IconList, IconPlus, IconSearch, IconUsers } from "@tabler/icons-react";
import { useState } from "react";
import { EmptyState, PageHeader } from "../../components/ui";
import { useFormat, useT } from "../../i18n";

interface TeamFee {
  name: string;
  active: boolean;
  amount: number | null;
}
interface Item {
  id: number;
  description: string;
  type: string;
  typeLabel: string;
  amount: number | null;
  bothPlayers: boolean;
  editUrl: string;
  teams: TeamFee[];
}
interface Props {
  items: Item[];
  canCreate: boolean;
  createUrl: string;
}

const TYPE_COLOR: Record<string, string> = {
  NORMAL: "brand",
  PER_ALL_OTHER_MATCHDAY_PLAYERS: "orange",
  MANUAL: "grape",
};

/** Penalty catalog: every item with its per-team fee + active state. */
export default function Catalog({ items, canCreate, createUrl }: Props) {
  const t = useT();
  const f = useFormat();
  const [query, setQuery] = useState("");
  const [type, setType] = useState("all");
  const types = Array.from(new Map(items.map((i) => [i.type, i.typeLabel])).entries());
  const shown = items.filter(
    (i) =>
      (type === "all" || i.type === type) &&
      i.description.toLowerCase().includes(query.trim().toLowerCase()),
  );
  return (
    <>
      <Head title={t("Penalty catalog")} />
      <PageHeader
        title={t("Penalty catalog")}
        subtitle={t("Fees and active flags per team; the edit page holds everything.")}
        left={<IconList size={40} stroke={1.5} />}
        actions={
          canCreate && (
            <Button component={Link} href={createUrl} leftSection={<IconPlus size={18} />}>
              {t("New item")}
            </Button>
          )
        }
      />
      {items.length === 0 ? (
        <EmptyState>{t("No catalog items yet.")}</EmptyState>
      ) : (
        <Stack gap="sm">
          <Group gap="sm" wrap="wrap">
            <TextInput
              placeholder={t("Search")}
              leftSection={<IconSearch size={16} />}
              value={query}
              onChange={(e) => setQuery(e.currentTarget.value)}
              style={{ flex: "1 1 220px" }}
            />
            {types.length > 1 && (
              <Box style={{ overflowX: "auto", maxWidth: "100%" }}>
                <SegmentedControl
                  value={type}
                  onChange={setType}
                  data={[{ value: "all", label: t("All") }, ...types.map(([value, label]) => ({ value, label: label.split(" – ")[0] }))]}
                />
              </Box>
            )}
          </Group>
          {shown.length === 0 && <EmptyState>{t("Nothing found.")}</EmptyState>}
          {shown.map((item) => (
            <Paper key={item.id} withBorder p="sm" radius="md">
              <Group justify="space-between" wrap="nowrap" align="flex-start" gap="sm">
                <Box style={{ minWidth: 0 }}>
                  <Text fw={800} fz="lg" style={{ overflowWrap: "anywhere" }}>{item.description}</Text>
                  <Group gap={6} mt={4}>
                    <Badge color={TYPE_COLOR[item.type] ?? "gray"} variant="light">{item.typeLabel}</Badge>
                    {item.bothPlayers && (
                      <Badge color="teal" variant="light" leftSection={<IconUsers size={12} />}>{t("Doubles: both players")}</Badge>
                    )}
                  </Group>
                </Box>
                <Button size="sm" color="yellow" component={Link} href={item.editUrl} leftSection={<IconEdit size={16} />} style={{ flexShrink: 0 }}>
                  {t("Edit")}
                </Button>
              </Group>
              {item.teams.length > 0 && (
                <Group gap={6} mt="sm">
                  {item.teams.map((team) => (
                    <Badge
                      key={team.name}
                      size="lg"
                      radius="sm"
                      variant={team.active ? "light" : "outline"}
                      color={team.active ? "green" : "gray"}
                      title={team.active ? t("active") : t("inactive")}
                      style={{ textTransform: "none", textDecoration: team.active ? undefined : "line-through" }}
                    >
                      {team.name} · {team.amount === null ? "–" : f.euro(team.amount)}
                    </Badge>
                  ))}
                </Group>
              )}
            </Paper>
          ))}
        </Stack>
      )}
    </>
  );
}
