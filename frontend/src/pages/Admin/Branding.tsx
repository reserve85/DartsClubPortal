import { Head, router } from "@inertiajs/react";
import { Box, Button, FileButton, Group, Image, Paper, SimpleGrid, Text } from "@mantine/core";
import { IconDownload, IconPhotoUp, IconTrash } from "@tabler/icons-react";
import { confirmPost } from "../../components/elo";
import { PageHeader } from "../../components/ui";
import { useT } from "../../i18n";

export default function Branding({ logo }: { logo: { light: string; dark: string } }) {
  const t = useT();
  const card = (kind: "light" | "dark", title: string, bg: string) => (
    <Paper withBorder p="md">
      <Text fw={800} mb="sm">{title}</Text>
      <Box h={120} mb="md" style={{ background: bg, borderRadius: 12, display: "grid", placeItems: "center" }}>
        {logo[kind] ? <Image src={logo[kind]} h={96} w="auto" fit="contain" /> : <Text c="dimmed" size="sm">{t("No logo yet")}</Text>}
      </Box>
      <Group>
        <FileButton accept="image/png,image/jpeg,image/webp,image/svg+xml" onChange={(f) => f && router.post("/club-logo/", { kind, logo: f }, { forceFormData: true })}>
          {(props) => <Button {...props} leftSection={<IconPhotoUp size={16} />}>{t("Upload")}</Button>}
        </FileButton>
        {logo[kind] && (
          <Button variant="default" component="a" href={logo[kind]} download={`club-logo-${kind}.png`} leftSection={<IconDownload size={16} />}>{t("Download")}</Button>
        )}
        {logo[kind] && (
          <Button
            color="red"
            variant="light"
            leftSection={<IconTrash size={16} />}
            onClick={() =>
              confirmPost({
                title: t("Remove the logo?"),
                body: t("Download it first if you want to keep it."),
                confirm: t("Remove"),
                cancel: t("Cancel"),
                url: "/club-logo/",
                data: { kind, remove: "1" },
              })
            }
          >
            {t("Remove")}
          </Button>
        )}
      </Group>
    </Paper>
  );
  return (
    <>
      <Head title={t("Club logo")} />
      <PageHeader title={t("Club logo")} subtitle={t("Shown in the header. Without a logo the dart badge is shown.")} />
      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        {card("light", t("Logo for light mode"), "#f5f7fb")}
        {card("dark", t("Logo for dark mode"), "#14161f")}
      </SimpleGrid>
      <Text size="xs" c="dimmed" mt="sm">{t("Tip: importing the Elo backup ZIP takes the old logos over automatically.")}</Text>
    </>
  );
}
