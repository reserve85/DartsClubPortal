import { usePage } from "@inertiajs/react";
import { Alert, Badge, Box, Button, Divider, Group, Modal, ScrollArea, Stack, Text } from "@mantine/core";
import { IconAlertTriangle, IconCheck } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { useT } from "../i18n";
import type { SharedProps } from "../types";

export interface NuligaTeamReport {
  team: string;
  ok: boolean;
  error: string;
  checked: number;
  first: boolean;
  items: { kind: "new" | "linked" | "changed" | "removed" | "noted"; label: string; changes: string[] }[];
}

const COLORS = { new: "teal", linked: "blue", changed: "orange", removed: "red", noted: "yellow" } as const;

/** Summary of a nuLiga sync: one dialog per run with every change in detail. */
export function NuligaReportDialog() {
  const t = useT();
  const { nuligaReport } = usePage<SharedProps>().props;
  const [report, setReport] = useState<NuligaTeamReport[] | null>(null);
  useEffect(() => {
    if (nuligaReport?.length) setReport(nuligaReport);
  }, [nuligaReport]);
  const kindLabel = {
    new: t("new"),
    linked: t("linked"),
    changed: t("changed"),
    removed: t("removed in nuLiga"),
    noted: t("not taken over"),
  };
  return (
    <Modal opened={!!report} onClose={() => setReport(null)} title={<Text fw={800}>{t("nuLiga sync")}</Text>} size="lg" centered scrollAreaComponent={ScrollArea.Autosize}>
      <Stack gap="md">
        {(report ?? []).map((r) => (
          <Box key={r.team}>
            <Group justify="space-between" mb={6}>
              <Text fw={800}>{r.team}</Text>
              {r.ok ? (
                <Badge color="teal" variant="light" leftSection={<IconCheck size={12} />}>
                  {t("%(n)s matchdays checked", { n: r.checked })}
                </Badge>
              ) : (
                <Badge color="red" variant="light">{t("failed")}</Badge>
              )}
            </Group>
            {!r.ok && (
              <Alert color="red" variant="light" icon={<IconAlertTriangle size={18} />}>
                <Text size="sm">{r.error}</Text>
                <Text size="xs" c="dimmed" mt={4}>{t("The portal tries again in about 1 hour.")}</Text>
              </Alert>
            )}
            {r.ok && r.items.length === 0 && <Text size="sm" c="dimmed">{t("Everything is up to date - nothing changed.")}</Text>}
            <Stack gap={6}>
              {r.items.map((item, i) => (
                <Group key={i} gap={8} wrap="nowrap" align="flex-start">
                  <Badge size="sm" color={COLORS[item.kind]} variant="light" style={{ flexShrink: 0 }} w={110}>
                    {kindLabel[item.kind]}
                  </Badge>
                  <Box style={{ minWidth: 0 }}>
                    <Text size="sm" fw={600}>{item.label}</Text>
                    {item.changes.map((c, j) => (
                      <Text key={j} size="xs" c="dimmed">→ {c}</Text>
                    ))}
                  </Box>
                </Group>
              ))}
            </Stack>
            <Divider mt="md" />
          </Box>
        ))}
        <Text size="xs" c="dimmed">{t("Every change is also in the audit log.")}</Text>
        <Group justify="flex-end">
          <Button onClick={() => setReport(null)}>{t("Close")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}
