import { Head, Link, usePage } from "@inertiajs/react";
import { Alert, Box, Button, Group, Image, Paper, Stack, Text, TextInput, Title } from "@mantine/core";
import { IconAlertTriangle, IconArrowLeft, IconPrinter } from "@tabler/icons-react";
import { useState } from "react";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { PageHeader } from "../../components/ui";
import { useT } from "../../i18n";
import type { SharedProps } from "../../types";

interface Props {
  target: { email: string; name: string; isClub: boolean };
  allowed: boolean;
  png: string;
  siteUrl: string;
  backUrl: string;
}

// Print: only the poster, on a white A4 page (footer, cookie notice etc. hidden).
const PRINT_CSS = `
@media print {
  @page { size: A4 portrait; margin: 14mm; }
  body * { visibility: hidden !important; }
  .qr-poster, .qr-poster * { visibility: visible !important; }
  .qr-poster { position: absolute; inset: 0; margin: 0 !important; border: 0 !important; box-shadow: none !important; background: #fff !important; }
  .qr-poster .poster-logo { height: 45mm !important; }
  .qr-poster .poster-qr { width: 125mm !important; height: 125mm !important; }
}`;

/** Printable poster for a shared club account: logo, headline, QR code, address. */
export default function UserQr({ target, allowed, png, siteUrl, backUrl }: Props) {
  const t = useT();
  const { site } = usePage<SharedProps>().props;
  const [headline, setHeadline] = useState(site.name);
  const [subline, setSubline] = useState(t("Enter Elo matches"));
  return (
    <>
      <Head title={t("QR login")} />
      <style>{PRINT_CSS}</style>
      <Box className="no-print">
        <PageHeader title={t("QR login")} subtitle={target.name ? `${target.name} · ${target.email}` : target.email} left={<PlayerAvatar name={target.name || target.email} size={52} />} />
      </Box>
      {allowed ? (
        <Stack gap="md" maw={640} mx="auto">
          <Paper withBorder p="md" className="no-print">
            <Stack gap="xs">
              <TextInput label={t("Headline")} value={headline} onChange={(e) => setHeadline(e.currentTarget.value)} />
              <TextInput label={t("Subline")} value={subline} onChange={(e) => setSubline(e.currentTarget.value)} />
              <Text size="xs" c="dimmed">{t("Changing the account's password makes every printed code invalid.")}</Text>
              <Group>
                <Button leftSection={<IconPrinter size={18} />} onClick={() => window.print()}>{t("Print poster")}</Button>
                <Button color="gray" component={Link} href={backUrl} leftSection={<IconArrowLeft size={18} />}>{t("Back")}</Button>
              </Group>
            </Stack>
          </Paper>

          <Paper className="qr-poster" withBorder radius="md" p={{ base: "lg", sm: 40 }} bg="white" ta="center">
            <Stack align="center" gap="lg">
              {site.logo.light && <Image className="poster-logo" src={site.logo.light} alt="" h={120} w="auto" fit="contain" />}
              <div>
                <Title order={1} fz={{ base: 30, sm: 44 }} lh={1.1} c="#111">{headline}</Title>
                {subline && <Text fz={{ base: 18, sm: 24 }} fw={600} mt={8} c="#444">{subline}</Text>}
              </div>
              <Image className="poster-qr" src={png} alt={t("QR code for the login")} w={320} h={320} style={{ imageRendering: "pixelated" }} />
              <Text fz={{ base: 16, sm: 20 }} fw={700} c="#111">{t("Scan the code with your phone camera.")}</Text>
              <div>
                <Text fz={14} c="#444">{t("Or open in the browser:")}</Text>
                <Text fz={{ base: 20, sm: 26 }} fw={800} c="#111" style={{ wordBreak: "break-all" }}>{siteUrl}</Text>
              </div>
            </Stack>
          </Paper>
        </Stack>
      ) : (
        <Paper withBorder p="lg" maw={520} mx="auto">
          <Stack>
            <Alert color="yellow" icon={<IconAlertTriangle />}>
              {target.isClub
                ? t("A QR code is only possible for active, approved accounts that are not admins and have a password.")
                : t("QR codes are only for club accounts (a shared login such as the tablet at the board). Tick “Club account” when editing the account.")}
            </Alert>
            <Group justify="center">
              <Button color="gray" component={Link} href={backUrl} leftSection={<IconArrowLeft size={18} />}>{t("Back")}</Button>
            </Group>
          </Stack>
        </Paper>
      )}
    </>
  );
}
