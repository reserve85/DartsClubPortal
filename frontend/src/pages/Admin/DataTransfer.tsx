import { Head, Link } from "@inertiajs/react";
import { Button, Group, Paper, SimpleGrid, Stack, Text } from "@mantine/core";
import { IconArchive, IconDatabaseExport, IconDatabaseImport, IconDownload, IconFileTypeCsv } from "@tabler/icons-react";
import type { ReactNode } from "react";
import { PageHeader } from "../../components/ui";
import { useT } from "../../i18n";

interface Props {
  can: { backup: boolean; import: boolean; csv: boolean };
  urls: { database: string; backup: string; import: string; csv: { href: string; label: "ranking" | "matches" | "players" }[] };
}

function Card({ icon, title, text, children }: { icon: ReactNode; title: string; text: string; children: ReactNode }) {
  return (
    <Paper withBorder p="md" radius="md">
      <Stack gap="sm">
        <Group gap="sm" wrap="nowrap">
          {icon}
          <Text fw={800}>{title}</Text>
        </Group>
        <Text size="sm" c="dimmed">{text}</Text>
        <Group gap="xs">{children}</Group>
      </Stack>
    </Paper>
  );
}

/** One place for the data: backup, CSV exports, import of the old systems. */
export default function DataTransfer({ can, urls }: Props) {
  const t = useT();
  const csvLabel = { ranking: t("Ranking (CSV)"), matches: t("Matches (CSV)"), players: t("Players (CSV)") };
  return (
    <>
      <Head title={t("Import & Export")} />
      <PageHeader title={t("Import & Export")} subtitle={t("Back up the data, export lists, take over the old systems.")} left={<IconDatabaseExport size={40} stroke={1.5} />} />
      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
        {can.backup && (
          <Card
            icon={<IconArchive size={24} />}
            title={t("Full backup")}
            text={t("Database, player pictures and club logo in one ZIP file. Keep it somewhere safe - it contains every account and every penalty.")}
          >
            <Button component="a" href={urls.backup} leftSection={<IconDownload size={16} />}>{t("Download backup (ZIP)")}</Button>
          </Card>
        )}
        {can.backup && (
          <Card
            icon={<IconDatabaseExport size={24} />}
            title={t("Database")}
            text={t("Only the database (.sqlite3), a consistent copy taken while the portal keeps running.")}
          >
            <Button variant="default" component="a" href={urls.database} leftSection={<IconDownload size={16} />}>{t("Download database")}</Button>
          </Card>
        )}
        {can.csv && (
          <Card
            icon={<IconFileTypeCsv size={24} />}
            title={t("Elo lists (CSV)")}
            text={t("For Excel: ranking of the current month, all matches, all players.")}
          >
            {urls.csv.map((c) => (
              <Button key={c.href} variant="default" size="sm" component="a" href={c.href} leftSection={<IconDownload size={14} />}>{csvLabel[c.label]}</Button>
            ))}
          </Card>
        )}
        {can.import && (
          <Card
            icon={<IconDatabaseImport size={24} />}
            title={t("Import")}
            text={t("Take over the data of the old Elo and penalty systems, with a preview first.")}
          >
            <Button variant="default" component={Link} href={urls.import} leftSection={<IconDatabaseImport size={16} />}>{t("Open import")}</Button>
          </Card>
        )}
      </SimpleGrid>
    </>
  );
}
