import { Head, Link, useForm } from "@inertiajs/react";
import { Alert, Avatar, Box, Button, Group, Paper, Stack, Table, Text } from "@mantine/core";
import { IconAlertTriangle, IconInfoCircle } from "@tabler/icons-react";
import { confirmPost } from "../../components/elo";
import { Field, FormFields, initialData, type FieldDef } from "../../components/FormFields";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { PasswordSetCard, type PasswordSet } from "../../components/PasswordSetCard";
import { PageHeader } from "../../components/ui";
import { useT } from "../../i18n";
import { colorFor } from "../../theme";
import { useState } from "react";

interface Props {
  title: string;
  subtitle?: string;
  badge?: string;
  badgePerson?: boolean;
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
  table?: FieldTable;
  /** Edit account: portal admins set a new password (with confirmation). */
  passwordSet?: PasswordSet | null;
}

/** Extra fields shown as a table (one row per object, e.g. per-team fees). */
interface FieldTable {
  title: string;
  help?: string;
  headers: string[];
  rows: { label: string; fields: string[] }[];
  /** Create only: typing into this field fills every untouched number cell. */
  copyFrom?: string;
  empty?: string;
  /** Inputs fill the cell (e.g. addresses). */
  wide?: boolean;
}

function TableFields({
  table,
  fields,
  data,
  setData,
  errors,
}: {
  table: FieldTable;
  fields: FieldDef[];
  data: Record<string, unknown>;
  setData: (n: string, v: unknown) => void;
  errors: Record<string, string>;
}) {
  const byName = new Map(fields.map((f) => [f.name, f]));
  return (
    <Stack gap={6}>
      <Text size="sm" fw={600}>{table.title}</Text>
      {table.rows.length === 0 ? (
        <Text size="sm" c="dimmed">{table.empty}</Text>
      ) : (
        <Box style={{ overflowX: "auto" }}>
          <Table verticalSpacing={6} highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                {table.headers.map((h, i) => (
                  <Table.Th key={h} ta={i === 1 ? "center" : undefined}>{h}</Table.Th>
                ))}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {table.rows.map((row) => (
                <Table.Tr key={row.label}>
                  <Table.Td fw={600} style={{ whiteSpace: "nowrap" }}>{row.label}</Table.Td>
                  {row.fields.map((name) => {
                    const f = byName.get(name);
                    if (!f) return <Table.Td key={name} />;
                    const compact = { ...f, label: "", help: "" };
                    return (
                      <Table.Td key={name} ta={f.type === "switch" ? "center" : undefined} miw={f.type === "number" ? 130 : table.wide ? 240 : undefined} w={table.wide ? "100%" : undefined}>
                        <Box display={table.wide ? "block" : "inline-block"} aria-label={`${f.label}: ${row.label}`}>
                          <Field
                            field={compact}
                            value={f.disabled ? f.value : data[name]}
                            onChange={(v) => setData(name, v)}
                            error={errors[name]}
                          />
                        </Box>
                      </Table.Td>
                    );
                  })}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Box>
      )}
      {table.help && <Text size="xs" c="dimmed">{table.help}</Text>}
    </Stack>
  );
}

/** Generic page for every plain Django form (create / edit, optional delete). */
export default function FormPage(p: Props) {
  const t = useT();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const form = useForm<Record<string, any>>(initialData(p.fields) as Record<string, any>);
  const errors: Record<string, string> = { ...p.errors, ...(form.errors as Record<string, string>) };
  const deleteLabel = p.deleteLabel ?? t("Delete");
  const tableNames = new Set((p.table?.rows ?? []).flatMap((r) => r.fields));
  const [touched] = useState(() => new Set<string>());
  const setField = (n: string, v: unknown) =>
    form.setData((d: Record<string, unknown>) => {
      const next = { ...d, [n]: v };
      if (p.table?.copyFrom && n === p.table.copyFrom) {
        // New entry: the default amount is copied into every untouched cell.
        for (const name of tableNames)
          if (!touched.has(name) && p.fields.find((f) => f.name === name)?.type === "number") next[name] = v;
      } else if (tableNames.has(n)) touched.add(n);
      return next;
    });
  return (
    <>
      <Head title={p.title} />
      <PageHeader
        title={p.title}
        subtitle={p.subtitle}
        left={
          p.badge ? (
            p.badgePerson ? (
              // A person: same initials as everywhere else (first + last name).
              <PlayerAvatar name={p.badge} size={48} />
            ) : (
              <Avatar color={colorFor(p.badge)} variant="filled" radius="xl" size={48}>
                {p.badge.slice(0, 2).toUpperCase()}
              </Avatar>
            )
          ) : undefined
        }
      />
      <Paper withBorder p={{ base: "md", sm: "lg" }} maw={760}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            form.post(p.action, { preserveScroll: "errors" });
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
              fields={p.fields.filter((f) => !tableNames.has(f.name))}
              data={form.data}
              setData={setField}
              errors={errors}
              rows={p.rows}
            />
            {p.table && (
              <TableFields table={p.table} fields={p.fields} data={form.data} setData={setField} errors={errors} />
            )}
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
      {p.passwordSet && (
        <Box maw={760} mt="md">
          <PasswordSetCard data={p.passwordSet} />
        </Box>
      )}
    </>
  );
}
