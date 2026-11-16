import { Head, Link, useForm } from "@inertiajs/react";
import { Alert, Avatar, Button, Group, Paper, Stack } from "@mantine/core";
import { IconAlertTriangle, IconInfoCircle } from "@tabler/icons-react";
import { confirmPost } from "../../components/elo";
import { FormFields, initialData, type FieldDef } from "../../components/FormFields";
import { PageHeader } from "../../components/ui";
import { useT } from "../../i18n";
import { colorFor } from "../../theme";

interface Props {
  title: string;
  subtitle?: string;
  badge?: string;
  fields: FieldDef[];
  errors: Record<string, string>;
  action: string;
  submitLabel?: string;
  cancelUrl?: string;
  deleteUrl?: string;
  deleteLabel?: string;
  deleteConfirm?: string;
  notice?: string;
  rows?: string[][];
}

/** Generic page for every plain Django form (create / edit, optional delete). */
export default function FormPage(p: Props) {
  const t = useT();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const form = useForm<Record<string, any>>(initialData(p.fields) as Record<string, any>);
  const errors: Record<string, string> = { ...p.errors, ...(form.errors as Record<string, string>) };
  const deleteLabel = p.deleteLabel ?? t("Delete");
  return (
    <>
      <Head title={p.title} />
      <PageHeader
        title={p.title}
        subtitle={p.subtitle}
        left={
          p.badge ? (
            <Avatar color={colorFor(p.badge)} variant="filled" radius="xl" size={48}>
              {p.badge.slice(0, 2).toUpperCase()}
            </Avatar>
          ) : undefined
        }
      />
      <Paper withBorder p={{ base: "md", sm: "lg" }} maw={760}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            form.post(p.action, { preserveScroll: true });
          }}
        >
          <Stack gap="lg">
            {p.notice && (
              <Alert color="blue" icon={<IconInfoCircle />}>
                {p.notice}
              </Alert>
            )}
            {errors.form && (
              <Alert color="red" icon={<IconAlertTriangle />}>
                {errors.form}
              </Alert>
            )}
            <FormFields
              fields={p.fields}
              data={form.data}
              setData={(n, v) => form.setData((d: Record<string, unknown>) => ({ ...d, [n]: v }))}
              errors={errors}
              rows={p.rows}
            />
            <Group justify="space-between" gap="sm">
              <Group gap="sm">
                <Button type="submit" loading={form.processing}>
                  {p.submitLabel ?? t("Save")}
                </Button>
                {p.cancelUrl && (
                  <Button color="gray" component={Link} href={p.cancelUrl}>
                    {t("Cancel")}
                  </Button>
                )}
              </Group>
              {p.deleteUrl && (
                <Button
                  color="red"
                  onClick={() =>
                    confirmPost({
                      title: deleteLabel,
                      body: p.deleteConfirm ?? t("Really delete? This cannot be undone."),
                      confirm: deleteLabel,
                      cancel: t("Cancel"),
                      url: p.deleteUrl!,
                    })
                  }
                >
                  {deleteLabel}
                </Button>
              )}
            </Group>
          </Stack>
        </form>
      </Paper>
    </>
  );
}
