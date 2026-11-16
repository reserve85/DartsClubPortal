import { Head, Link, router, useForm } from "@inertiajs/react";
import { Alert, Button, Group, Paper, Stack, Text } from "@mantine/core";
import { modals } from "@mantine/modals";
import { IconAlertTriangle, IconCheck, IconX } from "@tabler/icons-react";
import { FormFields, initialData, type FieldDef } from "../../components/FormFields";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { PageHeader } from "../../components/ui";
import { useFormat, useT } from "../../i18n";

interface Props {
  pendingUser: { id: number; email: string; name: string; joined: string | null };
  fields: FieldDef[];
  errors: Record<string, string>;
  action: string;
  backUrl: string;
}

export default function Approval({ pendingUser: u, fields, errors, action, backUrl }: Props) {
  const t = useT();
  const f = useFormat();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const form = useForm<Record<string, any>>({ ...(initialData(fields) as Record<string, any>), action: "approve" });
  const all = { ...errors, ...(form.errors as Record<string, string>) };
  const reject = () =>
    modals.openConfirmModal({
      title: t("Reject account"),
      children: <Text size="sm">{t("Reject %(name)s? The person is informed by e-mail and cannot log in.", { name: u.name || u.email })}</Text>,
      labels: { confirm: t("Reject"), cancel: t("Cancel") },
      confirmProps: { color: "red" },
      cancelProps: { variant: "filled", color: "gray" },
      onConfirm: () => router.post(action, { action: "reject" }),
    });
  return (
    <>
      <Head title={t("Review account")} />
      <PageHeader
        title={u.name || u.email}
        subtitle={`${u.email}${u.joined ? ` · ${t("registered")} ${f.date(u.joined)}` : ""}`}
        left={<PlayerAvatar name={u.name || u.email} size={52} />}
      />
      <Paper withBorder p={{ base: "md", sm: "lg" }} maw={760}>
        <form onSubmit={(e) => { e.preventDefault(); form.post(action, { preserveScroll: "errors" }); }}>
          <Stack gap="lg">
            <Text size="sm">{t("Link the account to an existing player, create a new player, or leave both empty for an account without player.")}</Text>
            {all.form && <Alert color="red" icon={<IconAlertTriangle />}>{all.form}</Alert>}
            <FormFields fields={fields} data={form.data} setData={(n, v) => form.setData((d: Record<string, unknown>) => ({ ...d, [n]: v }))} errors={all} />
            <Group justify="space-between" gap="sm">
              <Group gap="sm">
                <Button type="submit" color="teal" leftSection={<IconCheck size={18} />} loading={form.processing}>{t("Approve")}</Button>
                <Button color="gray" component={Link} href={backUrl}>{t("Cancel")}</Button>
              </Group>
              <Button color="red" leftSection={<IconX size={18} />} onClick={reject}>{t("Reject")}</Button>
            </Group>
          </Stack>
        </form>
      </Paper>
    </>
  );
}
