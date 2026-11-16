import { Head, Link } from "@inertiajs/react";
import { Box, Button, Group, Paper, Stack, Text } from "@mantine/core";
import { IconArrowLeft, IconUserCheck } from "@tabler/icons-react";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { EmptyState, PageHeader } from "../../components/ui";
import { useFormat, useT } from "../../i18n";

interface Props {
  users: { id: number; email: string; name: string; joined: string | null; reviewUrl: string }[];
}

export default function Pending({ users }: Props) {
  const t = useT();
  const f = useFormat();
  return (
    <>
      <Head title={t("Approvals")} />
      <PageHeader
        title={t("Approvals")}
        subtitle={t("Self-registered accounts can only log in after an admin approved them.")}
        left={<IconUserCheck size={40} stroke={1.5} />}
        actions={<Button color="gray" component={Link} href="/accounts/users/" leftSection={<IconArrowLeft size={18} />}>{t("Users")}</Button>}
      />
      {users.length === 0 ? (
        <EmptyState>{t("No account is waiting for approval.")}</EmptyState>
      ) : (
        <Stack gap="xs">
          {users.map((u) => (
            <Paper key={u.id} withBorder p="sm" radius="md" style={{ borderLeft: "4px solid var(--mantine-color-orange-filled)" }}>
              <Group wrap="nowrap" gap="sm">
                <PlayerAvatar name={u.name || u.email} size={40} />
                <Box style={{ minWidth: 0, flex: 1 }}>
                  <Text fw={800} truncate>{u.name || u.email}</Text>
                  <Text size="xs" c="dimmed" truncate>{u.email}{u.joined ? ` · ${t("registered")} ${f.date(u.joined)}` : ""}</Text>
                </Box>
                <Button color="orange" component={Link} href={u.reviewUrl} style={{ flexShrink: 0 }}>{t("Review")}</Button>
              </Group>
            </Paper>
          ))}
        </Stack>
      )}
    </>
  );
}
