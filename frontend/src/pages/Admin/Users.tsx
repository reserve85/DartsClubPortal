import { Head, Link, router } from "@inertiajs/react";
import { Badge, Box, Button, Group, Pagination, Paper, Stack, Text, TextInput } from "@mantine/core";
import { IconEdit, IconMailForward, IconQrcode, IconSearch, IconUserCheck, IconUserPlus, IconUsers } from "@tabler/icons-react";
import { useState } from "react";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { EmptyState, PageHeader } from "../../components/ui";
import { useFormat, useT } from "../../i18n";

interface UserRow {
  id: number;
  email: string;
  name: string;
  avatar: string;
  player: string;
  playerUrl: string | null;
  role: "system" | "admin" | "user" | "";
  team: string;
  status: "approved" | "pending" | "rejected" | "requested";
  active: boolean;
  lastLogin: string | null;
  editUrl: string | null;
  reviewUrl: string | null;
  qrUrl: string | null;
}
interface Props {
  users: UserRow[];
  pendingCount: number;
  inviteCount: number;
  page: number;
  pages: number;
}

const ROLE_COLOR = { system: "dark", admin: "brand", user: "gray", "": "gray" } as const;

export default function Users({ users, pendingCount, inviteCount, page, pages }: Props) {
  const t = useT();
  const f = useFormat();
  const [q, setQ] = useState("");
  const roleLabel = { system: t("System"), admin: t("Admin"), user: t("User"), "": t("no role") };
  const needle = q.trim().toLowerCase();
  const shown = users.filter((u) => !needle || `${u.name} ${u.email} ${u.player} ${u.team}`.toLowerCase().includes(needle));
  return (
    <>
      <Head title={t("Users")} />
      <PageHeader
        title={t("Users")}
        subtitle={t("Roles: System, Admin, User. Captain and cashier are assignments on top.")}
        left={<IconUsers size={40} stroke={1.5} />}
        actions={
          <>
            <Button component={Link} href="/accounts/users/pending/" color={pendingCount ? "orange" : undefined} leftSection={<IconUserCheck size={18} />}>
              {t("Approvals")} {pendingCount > 0 && <Badge ml={6} size="sm" color="white" c="orange" variant="filled">{pendingCount}</Badge>}
            </Button>
            <Button component={Link} href="/accounts/users/invitations/" leftSection={<IconMailForward size={18} />}>
              {t("Invitations")} {inviteCount > 0 && <Badge ml={6} size="sm" color="white" c="brand" variant="filled">{inviteCount}</Badge>}
            </Button>
            <Button component={Link} href="/accounts/users/create/" leftSection={<IconUserPlus size={18} />}>{t("New user")}</Button>
          </>
        }
      >
        <TextInput placeholder={t("Search")} leftSection={<IconSearch size={16} />} value={q} onChange={(e) => setQ(e.currentTarget.value)} />
      </PageHeader>

      {shown.length === 0 ? (
        <EmptyState>{needle ? t("Nothing found.") : t("No users yet.")}</EmptyState>
      ) : (
        <Stack gap="xs">
          {shown.map((u) => (
            <Paper key={u.id} withBorder p="sm" radius="md" style={{ opacity: u.active ? 1 : 0.6 }}>
              <Group wrap="nowrap" gap="sm" align="flex-start">
                <PlayerAvatar name={u.name || u.email} src={u.avatar} size={40} muted={!u.active} />
                <Box style={{ minWidth: 0, flex: 1 }}>
                  <Text fw={800} truncate>{u.name || u.email}</Text>
                  {u.name && <Text size="xs" c="dimmed" truncate>{u.email}</Text>}
                  <Group gap={6} mt={6}>
                    <Badge color={ROLE_COLOR[u.role]} variant={u.role ? "filled" : "outline"}>{roleLabel[u.role]}</Badge>
                    {u.team && <Badge color="yellow" variant="light">{t("Captain")}: {u.team}</Badge>}
                    {u.player && (
                      u.playerUrl ? (
                        <Badge component={Link} href={u.playerUrl} variant="light" color="teal" style={{ cursor: "pointer", textTransform: "none" }}>{u.player}</Badge>
                      ) : (
                        <Badge variant="light" color="teal" style={{ textTransform: "none" }}>{u.player}</Badge>
                      )
                    )}
                    {u.status === "pending" && <Badge color="orange">{t("waiting for approval")}</Badge>}
                    {u.status === "rejected" && <Badge color="red" variant="light">{t("rejected")}</Badge>}
                    {u.status === "requested" && <Badge color="cyan" variant="light">{t("invited")}</Badge>}
                    {!u.active && <Badge color="gray">{t("inactive")}</Badge>}
                  </Group>
                  {u.lastLogin && <Text size="xs" c="dimmed" mt={6}>{t("Last login")}: {f.date(u.lastLogin)}</Text>}
                </Box>
                <Stack gap={6} align="flex-end" style={{ flexShrink: 0 }}>
                  {u.reviewUrl && <Button size="compact-sm" color="orange" component={Link} href={u.reviewUrl}>{t("Review")}</Button>}
                  {u.status === "requested" && <Button size="compact-sm" component={Link} href="/accounts/users/invitations/">{t("Invitations")}</Button>}
                  {u.editUrl && <Button size="compact-sm" color="yellow" component={Link} href={u.editUrl} leftSection={<IconEdit size={14} />}>{t("Edit")}</Button>}
                  {u.qrUrl && <Button size="compact-sm" component={Link} href={u.qrUrl} leftSection={<IconQrcode size={14} />}>QR</Button>}
                </Stack>
              </Group>
            </Paper>
          ))}
        </Stack>
      )}
      {pages > 1 && (
        <Group justify="center" mt="lg">
          <Pagination total={pages} value={page} onChange={(n) => router.get("/accounts/users/", { page: n }, { preserveScroll: true })} />
        </Group>
      )}
    </>
  );
}
