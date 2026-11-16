import { Head, Link, router } from "@inertiajs/react";
import { Badge, Box, Button, Group, Paper, Stack, Text } from "@mantine/core";
import { IconCalendarEvent, IconEdit, IconPlus, IconStar } from "@tabler/icons-react";
import { EmptyState, PageHeader } from "../../components/ui";
import { useT, useTn } from "../../i18n";

interface Season {
  id: number;
  name: string;
  isDefault: boolean;
  matchdays: number;
  payments: number;
  teams: number;
  editUrl: string;
  defaultUrl: string;
}

export default function Seasons({ seasons }: { seasons: Season[] }) {
  const t = useT();
  const tn = useTn();
  return (
    <>
      <Head title={t("Seasons")} />
      <PageHeader
        title={t("Seasons")}
        subtitle={t("Every season is a closed cash box. The default season is what every user sees first.")}
        left={<IconCalendarEvent size={40} stroke={1.5} />}
        actions={
          <Button component={Link} href="/seasons/create/" leftSection={<IconPlus size={18} />}>
            {t("New season")}
          </Button>
        }
      />
      {seasons.length === 0 ? (
        <EmptyState>{t("No seasons yet.")}</EmptyState>
      ) : (
        <Stack gap="xs">
          {seasons.map((s) => (
            <Paper key={s.id} withBorder p="sm" radius="md" style={s.isDefault ? { borderColor: "var(--mantine-color-brand-filled)" } : undefined}>
              <Group justify="space-between" wrap="wrap" gap="sm">
                <Box style={{ minWidth: 0 }}>
                  <Group gap={8}>
                    <Text fw={800} fz="lg">{s.name}</Text>
                    {s.isDefault && <Badge color="brand" variant="filled" leftSection={<IconStar size={12} />}>{t("Default")}</Badge>}
                  </Group>
                  <Text size="sm" c="dimmed" mt={2}>
                    {[
                      s.teams ? tn("%(n)s team", "%(n)s teams", s.teams) : t("all teams"),
                      tn("%(n)s matchday", "%(n)s matchdays", s.matchdays),
                      tn("%(n)s payment", "%(n)s payments", s.payments),
                    ].join(" · ")}
                  </Text>
                </Box>
                <Group gap="xs">
                  {!s.isDefault && (
                    <Button size="sm" onClick={() => router.post(s.defaultUrl, {}, { preserveScroll: true })}>
                      {t("Make default")}
                    </Button>
                  )}
                  <Button size="sm" color="yellow" component={Link} href={s.editUrl} leftSection={<IconEdit size={16} />}>
                    {t("Edit")}
                  </Button>
                </Group>
              </Group>
            </Paper>
          ))}
        </Stack>
      )}
    </>
  );
}
