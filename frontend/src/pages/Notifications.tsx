import { Head, Link, router } from "@inertiajs/react";
import { Badge, Box, Button, Group, Indicator, Pagination, Paper, SegmentedControl, Stack, Text, ThemeIcon } from "@mantine/core";
import { modals } from "@mantine/modals";
import { IconBell, IconChecks, IconMail, IconMailOpened, IconTrash } from "@tabler/icons-react";
import dayjs from "dayjs";
import { EmptyState, PageHeader } from "../components/ui";
import { useT } from "../i18n";

interface Row {
  id: number;
  verb: string;
  actor: string;
  when: string;
  unread: boolean;
  reviewUrl: string | null;
  toggleUrl: string;
  deleteUrl: string;
}
interface Props {
  tab: "unread" | "all";
  rows: Row[];
  page: number;
  pages: number;
  unreadCount: number;
  urls: { all: string; unread: string; markAll: string; deleteRead: string };
}

export default function Notifications({ tab, rows, page, pages, unreadCount, urls }: Props) {
  const t = useT();
  const opts = { preserveScroll: true };
  const confirm = (title: string, url: string) =>
    modals.openConfirmModal({
      title,
      labels: { confirm: t("Delete"), cancel: t("Cancel") },
      confirmProps: { color: "red" },
      cancelProps: { variant: "filled", color: "gray" },
      onConfirm: () => router.post(url, {}, opts),
    });
  return (
    <>
      <Head title={t("Notifications")} />
      <PageHeader
        title={t("Notifications")}
        left={<ThemeIcon size={44} radius="xl" variant="light"><IconBell size={24} /></ThemeIcon>}
        actions={
          <>
            <Button size="sm" leftSection={<IconChecks size={16} />} disabled={unreadCount === 0} onClick={() => router.get(urls.markAll, {}, opts)}>
              {t("Mark all as read")}
            </Button>
            <Button size="sm" color="red" leftSection={<IconTrash size={16} />} onClick={() => confirm(t("Delete all read messages?"), urls.deleteRead)}>
              {t("Delete read messages")}
            </Button>
          </>
        }
      >
        <SegmentedControl
          value={tab}
          onChange={(v) => router.get(v === "unread" ? urls.unread : urls.all, {}, { preserveScroll: true })}
          data={[
            { value: "unread", label: `${t("Unread")} (${unreadCount})` },
            { value: "all", label: t("All") },
          ]}
        />
      </PageHeader>

      {rows.length === 0 ? (
        <EmptyState>{t("No notifications yet.")}</EmptyState>
      ) : (
        <Stack gap="xs">
          {rows.map((n) => (
            <Paper key={n.id} withBorder p="sm" radius="md" style={n.unread ? { borderLeft: "4px solid var(--mantine-color-dart-filled)" } : undefined}>
              <Group wrap="nowrap" align="flex-start" gap="sm">
                <Indicator disabled={!n.unread} color="dart" size={9} offset={4}>
                  <ThemeIcon variant="light" color={n.unread ? "dart" : "gray"} radius="xl" size={34}>
                    {n.unread ? <IconMail size={18} /> : <IconMailOpened size={18} />}
                  </ThemeIcon>
                </Indicator>
                <Box style={{ minWidth: 0, flex: 1 }}>
                  <Text fw={n.unread ? 800 : 600} size="sm">{n.verb}</Text>
                  <Text size="xs" c="dimmed">
                    {[n.actor, dayjs(n.when).format("DD.MM.YYYY HH:mm")].filter(Boolean).join(" · ")}
                  </Text>
                  <Group gap={6} mt={8}>
                    {n.reviewUrl && (
                      <Button size="compact-sm" component={Link} href={n.reviewUrl}>{t("Review")}</Button>
                    )}
                    <Button size="compact-sm" color="gray" onClick={() => router.get(n.toggleUrl, {}, opts)}>
                      {n.unread ? t("Mark as read") : t("Mark as unread")}
                    </Button>
                    <Button size="compact-sm" color="red" onClick={() => confirm(t("Delete this message?"), n.deleteUrl)}>
                      {t("Delete")}
                    </Button>
                  </Group>
                </Box>
                {n.unread && <Badge color="dart" variant="light" style={{ flexShrink: 0 }}>{t("new")}</Badge>}
              </Group>
            </Paper>
          ))}
        </Stack>
      )}
      {pages > 1 && (
        <Group justify="center" mt="lg">
          <Pagination total={pages} value={page} onChange={(p) => router.get(tab === "unread" ? urls.unread : urls.all, { page: p }, opts)} />
        </Group>
      )}
    </>
  );
}
