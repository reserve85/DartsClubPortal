import { Head, Link, router, useForm } from "@inertiajs/react";
import { Alert, Button, Group, Paper, Stack } from "@mantine/core";
import { modals } from "@mantine/modals";
import { IconAlertTriangle, IconUsersGroup } from "@tabler/icons-react";
import { FormFields, initialData, type FieldDef } from "../../components/FormFields";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { PageHeader } from "../../components/ui";
import { useT } from "../../i18n";

interface Props {
  penalty: { id: number; player: string; playerAvatar: string; catalog: string; matchday: string; matchdayId: number };
  deleteUrl: string;
  groupCount: number;
  groupPlayers: string;
  fields: FieldDef[];
  errors: Record<string, string>;
}

export default function PenaltyEdit({ penalty: p, deleteUrl, groupCount, groupPlayers, fields, errors }: Props) {
  const t = useT();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const form = useForm<Record<string, any>>(initialData(fields) as Record<string, any>);
  const group = groupCount > 1;
  const del = (scope: "single" | "group") =>
    modals.openConfirmModal({
      title: t("Delete penalty"),
      children: scope === "group" && group ? t("Delete this penalty for all players of the group?") : t("Delete this penalty?"),
      labels: { confirm: t("Delete"), cancel: t("Cancel") },
      confirmProps: { color: "red" },
      cancelProps: { variant: "filled", color: "gray" },
      onConfirm: () => router.post(deleteUrl, { scope }),
    });
  return (
    <>
      <Head title={t("Edit penalty")} />
      <PageHeader
        title={t("Edit penalty")}
        subtitle={[p.player, p.catalog, p.matchday].filter(Boolean).join(" · ")}
        left={<PlayerAvatar name={p.player} src={p.playerAvatar} size={52} />}
      />
      <Paper withBorder p={{ base: "md", sm: "lg" }} maw={760}>
        <form onSubmit={(e) => { e.preventDefault(); form.post(`/penalties/${p.id}/edit/`, { preserveScroll: true }); }}>
          <Stack gap="lg">
            {group && (
              <Alert color="grape" icon={<IconUsersGroup />}>
                {t("Group penalty of %(n)s players: %(names)s. Changes apply to every row of the group.", { n: groupCount, names: groupPlayers })}
              </Alert>
            )}
            {errors.form && <Alert color="red" icon={<IconAlertTriangle />}>{errors.form}</Alert>}
            <FormFields fields={fields} data={form.data} setData={(n, v) => form.setData((d: Record<string, unknown>) => ({ ...d, [n]: v }))} errors={errors} />
            <Group justify="space-between" gap="sm">
              <Group gap="sm">
                <Button type="submit" loading={form.processing}>{t("Save changes")}</Button>
                <Button color="gray" component={Link} href={`/matchdays/${p.matchdayId}/`}>{t("Cancel")}</Button>
              </Group>
              <Group gap="sm">
                {group && <Button color="red" variant="filled" onClick={() => del("single")}>{t("Delete for this player")}</Button>}
                <Button color="red" onClick={() => del("group")}>{group ? t("Delete for the whole group") : t("Delete")}</Button>
              </Group>
            </Group>
          </Stack>
        </form>
      </Paper>
    </>
  );
}
