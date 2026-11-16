import { Head, Link, router, useForm } from "@inertiajs/react";
import { Accordion, Alert, Badge, Button, FileInput, Group, Paper, SegmentedControl, Select, SimpleGrid, Stack, Switch, Table, Text, TextInput, ThemeIcon } from "@mantine/core";
import { modals } from "@mantine/modals";
import { IconAlertTriangle, IconCheck, IconDatabaseImport, IconFileUpload, IconX } from "@tabler/icons-react";
import { useState } from "react";
import { PageHeader, Section, StatTile } from "../../components/ui";
import { useT } from "../../i18n";

interface Report {
  kind: string;
  ok: boolean;
  counts: { label: string; value: number }[];
  checks: { label: string; ok: boolean; detail: string }[];
  warnings: string[];
  matched: { what: string; source: string; portal: string }[];
}
interface Props {
  stage: "upload" | "preview" | "done";
  report: Report | null;
  pending: { name: string; kind: string; accounts: { id: number; username: string; role: string }[] } | null;
  portalUsers: { value: string; label: string }[];
}

function ReportView({ report }: { report: Report }) {
  const t = useT();
  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 2, sm: 3, md: 4 }} spacing="xs">
        {report.counts.map((c) => (
          <StatTile key={c.label} label={c.label} value={c.value} />
        ))}
      </SimpleGrid>
      {report.checks.length > 0 && (
        <Paper withBorder radius="md">
          <Table verticalSpacing={6}>
            <Table.Tbody>
              {report.checks.map((c) => (
                <Table.Tr key={c.label}>
                  <Table.Td w={36}>
                    <ThemeIcon size="sm" radius="xl" color={c.ok ? "teal" : "red"}>{c.ok ? <IconCheck size={12} /> : <IconX size={12} />}</ThemeIcon>
                  </Table.Td>
                  <Table.Td fw={600}>{c.label}</Table.Td>
                  <Table.Td c="dimmed" fz="sm">{c.detail}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      )}
      {report.warnings.length > 0 && (
        <Alert color="yellow" icon={<IconAlertTriangle />}>
          <Stack gap={4}>{report.warnings.map((w, i) => <Text key={i} size="sm">{w}</Text>)}</Stack>
        </Alert>
      )}
      {report.matched.length > 0 && (
        <Accordion variant="contained">
          <Accordion.Item value="matched">
            <Accordion.Control>{t("Matched with existing entries (%(n)s)", { n: report.matched.length })}</Accordion.Control>
            <Accordion.Panel>
              <Stack gap={2}>
                {report.matched.map((m, i) => (
                  <Text key={i} size="sm">{m.what}: {m.source} → {m.portal}</Text>
                ))}
              </Stack>
            </Accordion.Panel>
          </Accordion.Item>
        </Accordion>
      )}
    </Stack>
  );
}

export default function Import({ stage, report, pending, portalUsers }: Props) {
  const t = useT();
  const upload = useForm<{ action: string; kind: string; file: File | null; replace: boolean; email_domain: string }>({
    action: "preview",
    kind: "penalty",
    file: null,
    replace: false,
    email_domain: "",
  });
  const [map, setMap] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const run = () =>
    modals.openConfirmModal({
      title: t("Import now"),
      children: <Text size="sm">{t("Import the data now?")}</Text>,
      labels: { confirm: t("Import now"), cancel: t("Cancel") },
      confirmProps: { color: "teal" },
      cancelProps: { variant: "filled", color: "gray" },
      onConfirm: () =>
        router.post(
          "/import/",
          { action: "run", ...Object.fromEntries(Object.entries(map).filter(([, v]) => v).map(([k, v]) => [`map_${k}`, v])) },
          { onStart: () => setBusy(true), onFinish: () => setBusy(false) },
        ),
    });

  return (
    <>
      <Head title={t("Import")} />
      <PageHeader title={t("Import")} subtitle={t("Take over the data of the old Elo and penalty systems.")} left={<IconDatabaseImport size={40} stroke={1.5} />} />

      {stage === "upload" && (
        <Paper withBorder p={{ base: "md", sm: "lg" }} maw={760}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              upload.post("/import/", { forceFormData: true });
            }}
          >
            <Stack gap="md">
              <div>
                <Text size="sm" fw={500} mb={6}>{t("Database")}</Text>
                <SegmentedControl
                  fullWidth
                  value={upload.data.kind}
                  onChange={(v) => upload.setData("kind", v)}
                  data={[
                    { value: "penalty", label: "Penalty" },
                    { value: "elo", label: "Elo" },
                  ]}
                />
              </div>
              <FileInput
                label={t("File")}
                required
                clearable
                leftSection={<IconFileUpload size={16} />}
                placeholder={upload.data.kind === "elo" ? "database.db / backup.zip" : "db.sqlite3"}
                value={upload.data.file}
                onChange={(f) => upload.setData("file", f)}
              />
              {upload.data.kind === "elo" && (
                <Paper withBorder p="sm" radius="md">
                  <Stack gap="sm">
                    <Text size="sm" fw={700}>{t("Options for the Elo import")}</Text>
                    <Switch label={t("Replace existing Elo data")} checked={upload.data.replace} onChange={(e) => upload.setData("replace", e.currentTarget.checked)} />
                    <TextInput label={t("E-mail domain for new accounts")} placeholder="elo.invalid" value={upload.data.email_domain} onChange={(e) => upload.setData("email_domain", e.currentTarget.value)} />
                  </Stack>
                </Paper>
              )}
              <Text size="sm" c="dimmed">{t("Recommended order: penalty database first (it has the e-mail addresses), then the Elo database. You always see a preview first.")}</Text>
              <Group>
                <Button type="submit" disabled={!upload.data.file} loading={upload.processing}>{t("Show preview")}</Button>
              </Group>
            </Stack>
          </form>
        </Paper>
      )}

      {stage !== "upload" && report && (
        <Section
          title={stage === "done" ? t("Result") : t("Preview – nothing has been saved yet")}
          right={<Badge color={report.ok ? "teal" : "red"} variant="filled">{report.ok ? t("all checks passed") : t("checks failed")}</Badge>}
        >
          {pending?.name && <Text size="sm" c="dimmed" mb="sm">{pending.name}</Text>}
          <ReportView report={report} />
        </Section>
      )}

      {stage === "preview" && pending && (
        <>
          {pending.accounts.length > 0 && (
            <Section title={t("Elo accounts")}>
              <Text size="sm" c="dimmed" mb="sm">
                {t("Elo logins have no e-mail address. Link them to an existing portal account, or a new account is created (login name kept for old QR codes).")}
              </Text>
              <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
                {pending.accounts.map((acc) => (
                  <Select
                    key={acc.id}
                    label={<Group gap={6}>{acc.username}<Badge size="xs" variant="light">{acc.role}</Badge></Group>}
                    data={[{ value: "", label: t("— create a new account —") }, ...portalUsers]}
                    value={map[acc.id] ?? ""}
                    onChange={(v) => setMap((m) => ({ ...m, [acc.id]: v ?? "" }))}
                    searchable
                    allowDeselect={false}
                  />
                ))}
              </SimpleGrid>
            </Section>
          )}
          <Group mt="lg">
            <Button color="teal" leftSection={<IconCheck size={18} />} onClick={run} loading={busy} disabled={!report?.ok}>{t("Import now")}</Button>
            <Button color="gray" component={Link} href="/import/">{t("Cancel")}</Button>
          </Group>
        </>
      )}

      {stage === "done" && (
        <Group mt="lg">
          <Button component={Link} href="/import/">{t("Import another file")}</Button>
        </Group>
      )}
    </>
  );
}
