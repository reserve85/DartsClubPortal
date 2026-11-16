import { Head, router } from "@inertiajs/react";
import { Badge, Box, Code, Group, Pagination, Paper, Select, Stack, Text, TextInput } from "@mantine/core";
import { useDebouncedCallback } from "@mantine/hooks";
import { IconHistory, IconSearch } from "@tabler/icons-react";
import dayjs from "dayjs";
import { useState } from "react";
import { EmptyState, PageHeader } from "../../components/ui";
import { useT, useTn } from "../../i18n";

interface Entry {
  id: number;
  when: string;
  action: string;
  actionLabel: string;
  user: string;
  target: string;
  metadata: Record<string, unknown>;
}
interface Props {
  entries: Entry[];
  actions: { value: string; label: string }[];
  action: string;
  actor: string;
  page: number;
  pages: number;
  total: number;
}

function color(action: string) {
  if (/DELETE|REJECT|DEACTIVAT|CANCEL/i.test(action)) return "red";
  if (/CREATE|APPROV|ACCEPT|SENT/i.test(action)) return "teal";
  if (/LOGIN|LOGOUT/i.test(action)) return "gray";
  return "brand";
}

export default function Audit({ entries, actions, action, actor, page, pages, total }: Props) {
  const t = useT();
  const tn = useTn();
  const [who, setWho] = useState(actor);
  const go = (params: Record<string, string | number>) =>
    router.get("/audit/", { action, actor: who, ...params }, { preserveState: true, preserveScroll: true, replace: true });
  const search = useDebouncedCallback((v: string) => go({ actor: v, page: 1 }), 350);
  return (
    <>
      <Head title={t("Audit log")} />
      <PageHeader
        title={t("Audit log")}
        subtitle={tn("%(n)s entry", "%(n)s entries", total)}
        left={<IconHistory size={40} stroke={1.5} />}
      >
        <Group gap="sm" wrap="wrap">
          <Select
            placeholder={t("All actions")}
            data={actions}
            value={action || null}
            onChange={(v) => go({ action: v ?? "", page: 1 })}
            clearable
            searchable
            style={{ flex: "1 1 14rem" }}
          />
          <TextInput
            placeholder={t("User (e-mail)")}
            leftSection={<IconSearch size={16} />}
            value={who}
            onChange={(e) => {
              setWho(e.currentTarget.value);
              search(e.currentTarget.value);
            }}
            style={{ flex: "1 1 14rem" }}
          />
        </Group>
      </PageHeader>
      {entries.length === 0 ? (
        <EmptyState>{t("No entries yet.")}</EmptyState>
      ) : (
        <Stack gap={6}>
          {entries.map((e) => (
            <Paper key={e.id} withBorder p="xs" px="sm" radius="md">
              <Group justify="space-between" wrap="nowrap" align="flex-start" gap="sm">
                <Box style={{ minWidth: 0 }}>
                  <Group gap={6}>
                    <Badge color={color(e.action)} variant="light" style={{ textTransform: "none" }}>{e.actionLabel}</Badge>
                    {e.target && <Code>{e.target}</Code>}
                  </Group>
                  <Text size="xs" c="dimmed" mt={4}>{e.user || t("system")}</Text>
                  {Object.keys(e.metadata).length > 0 && (
                    <Text size="xs" c="dimmed" mt={2} style={{ overflowWrap: "anywhere", fontFamily: "var(--mantine-font-family-monospace)" }}>
                      {Object.entries(e.metadata).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`).join(" · ")}
                    </Text>
                  )}
                </Box>
                <Text size="xs" c="dimmed" className="num" style={{ whiteSpace: "nowrap" }}>{dayjs(e.when).format("DD.MM.YY HH:mm")}</Text>
              </Group>
            </Paper>
          ))}
        </Stack>
      )}
      {pages > 1 && (
        <Group justify="center" mt="lg">
          <Pagination total={pages} value={page} onChange={(n) => go({ page: n })} />
        </Group>
      )}
    </>
  );
}
