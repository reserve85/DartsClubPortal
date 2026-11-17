import { Head, Link, router } from "@inertiajs/react";
import { ActionIcon, Badge, Box, Button, CopyButton, Group, Pagination, Paper, Stack, Text, TextInput, Tooltip } from "@mantine/core";
import { modals } from "@mantine/modals";
import { IconArrowLeft, IconCheck, IconCopy, IconMailForward, IconPlus } from "@tabler/icons-react";
import { EmptyState, PageHeader } from "../../components/ui";
import { useFormat, useT } from "../../i18n";

interface Invite {
  id: number;
  email: string;
  role: string;
  team: string;
  player: string;
  invitedBy: string;
  created: string | null;
  accepted: string | null;
  expires: string | null;
  status: "open" | "expiring" | "expired" | "accepted";
  link: string | null;
  resendUrl: string | null;
  cancelUrl: string | null;
}
interface Props {
  invitations: Invite[];
  page: number;
  pages: number;
}

const STATUS_COLOR = { open: "teal", expiring: "orange", expired: "red", accepted: "gray" } as const;

export default function Invites({ invitations, page, pages }: Props) {
  const t = useT();
  const f = useFormat();
  const statusLabel = { open: t("open"), expiring: t("expires soon"), expired: t("expired"), accepted: t("accepted") };
  const cancel = (inv: Invite) =>
    modals.openConfirmModal({
      modalId: "confirm", // one at a time: a double tap must not stack a second dialog
      title: t("Cancel invitation"),
      children: <Text size="sm">{t("Cancel the invitation for %(email)s? The prepared account is deleted.", { email: inv.email })}</Text>,
      labels: { confirm: t("Cancel invitation"), cancel: t("Back") },
      confirmProps: { color: "red" },
      cancelProps: { variant: "filled", color: "gray" },
      onConfirm: () => router.post(inv.cancelUrl!, {}, { preserveScroll: true }),
    });
  return (
    <>
      <Head title={t("Invitations")} />
      <PageHeader
        title={t("Invitations")}
        subtitle={t("Invited people set their own password via the link in the e-mail.")}
        left={<IconMailForward size={40} stroke={1.5} />}
        actions={
          <>
            <Button color="gray" component={Link} href="/accounts/users/" leftSection={<IconArrowLeft size={18} />}>{t("Users")}</Button>
            <Button component={Link} href="/accounts/users/invitations/create/" leftSection={<IconPlus size={18} />}>{t("New invitation")}</Button>
          </>
        }
      />
      {invitations.length === 0 ? (
        <EmptyState>{t("No invitations yet.")}</EmptyState>
      ) : (
        <Stack gap="xs">
          {invitations.map((inv) => (
            <Paper key={inv.id} withBorder p="sm" radius="md" style={{ opacity: inv.status === "accepted" ? 0.7 : 1 }}>
              <Group justify="space-between" wrap="nowrap" align="flex-start" gap="sm">
                <Box style={{ minWidth: 0 }}>
                  <Text fw={800} truncate>{inv.email}</Text>
                  <Group gap={6} mt={6}>
                    <Badge color={STATUS_COLOR[inv.status]} variant={inv.status === "accepted" ? "light" : "filled"}>{statusLabel[inv.status]}</Badge>
                    <Badge color="brand" variant="light">{inv.role}</Badge>
                    {inv.team && <Badge color="yellow" variant="light">{t("Captain")}: {inv.team}</Badge>}
                    {inv.player && <Badge color="teal" variant="light" style={{ textTransform: "none" }}>{inv.player}</Badge>}
                  </Group>
                  <Text size="xs" c="dimmed" mt={6}>
                    {inv.created && `${t("invited")} ${f.date(inv.created)}`}
                    {inv.invitedBy && ` · ${inv.invitedBy}`}
                    {inv.accepted ? ` · ${t("accepted")} ${f.date(inv.accepted)}` : inv.expires ? ` · ${t("valid until")} ${f.date(inv.expires)}` : ""}
                  </Text>
                </Box>
              </Group>
              {(inv.link || inv.resendUrl) && (
                <Group gap="xs" mt="sm" wrap="nowrap">
                  {inv.link && (
                    <TextInput size="xs" value={inv.link} readOnly style={{ flex: 1, minWidth: 0 }} onFocus={(e) => e.currentTarget.select()}
                      rightSection={
                        <CopyButton value={inv.link}>
                          {({ copied, copy }) => (
                            <Tooltip label={copied ? t("Copied") : t("Copy link")}>
                              <ActionIcon variant="filled" color={copied ? "teal" : "brand"} size="sm" onClick={copy} aria-label={t("Copy link")}>
                                {copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
                              </ActionIcon>
                            </Tooltip>
                          )}
                        </CopyButton>
                      }
                    />
                  )}
                  {!inv.link && inv.status === "expired" && <Text size="xs" c="dimmed" style={{ flex: 1 }}>{t("Resend first to get a new link.")}</Text>}
                  {inv.resendUrl && <Button size="xs" onClick={() => router.post(inv.resendUrl!, {}, { preserveScroll: true })}>{t("Resend")}</Button>}
                  {inv.cancelUrl && <Button size="xs" color="red" onClick={() => cancel(inv)}>{t("Cancel")}</Button>}
                </Group>
              )}
            </Paper>
          ))}
        </Stack>
      )}
      {pages > 1 && (
        <Group justify="center" mt="lg">
          <Pagination total={pages} value={page} onChange={(n) => router.get("/accounts/users/invitations/", { page: n }, { preserveScroll: true })} />
        </Group>
      )}
    </>
  );
}
