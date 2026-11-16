import { Head, Link } from "@inertiajs/react";
import { Alert, Button, Group, Image, Paper, Stack, Text } from "@mantine/core";
import { IconAlertTriangle, IconArrowLeft, IconPrinter } from "@tabler/icons-react";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { PageHeader } from "../../components/ui";
import { useT } from "../../i18n";

interface Props {
  target: { email: string; name: string };
  allowed: boolean;
  png: string;
  backUrl: string;
}

export default function UserQr({ target, allowed, png, backUrl }: Props) {
  const t = useT();
  return (
    <>
      <Head title={t("QR login")} />
      <PageHeader title={t("QR login")} subtitle={target.name ? `${target.name} · ${target.email}` : target.email} left={<PlayerAvatar name={target.name || target.email} size={52} />} />
      <Paper withBorder p="lg" maw={520} mx="auto" ta="center">
        {allowed ? (
          <Stack align="center" gap="md">
            <Paper p="sm" bg="white" radius="md">
              <Image src={png} alt={t("QR code for the login")} w={280} h={280} style={{ imageRendering: "pixelated" }} />
            </Paper>
            <Text size="sm" c="dimmed">
              {t("Scanning this code logs in this account without a password – print it only for shared club accounts (e.g. the tablet at the board).")}
            </Text>
            <Text size="sm" c="dimmed">{t("Changing the account's password makes every printed code invalid.")}</Text>
            <Group justify="center" className="no-print">
              <Button leftSection={<IconPrinter size={18} />} onClick={() => window.print()}>{t("Print")}</Button>
              <Button color="gray" component={Link} href={backUrl} leftSection={<IconArrowLeft size={18} />}>{t("Back")}</Button>
            </Group>
          </Stack>
        ) : (
          <Stack>
            <Alert color="yellow" icon={<IconAlertTriangle />} ta="left">
              {t("A QR code is only possible for active, approved accounts that are not admins and have a password.")}
            </Alert>
            <Group justify="center">
              <Button color="gray" component={Link} href={backUrl} leftSection={<IconArrowLeft size={18} />}>{t("Back")}</Button>
            </Group>
          </Stack>
        )}
      </Paper>
    </>
  );
}
