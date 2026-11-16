import { router } from "@inertiajs/react";
import { Button, FileButton, Group, Paper, Text } from "@mantine/core";
import { IconPhotoUp, IconTrash } from "@tabler/icons-react";
import { useState } from "react";
import { useT } from "../i18n";
import { PlayerAvatar } from "./PlayerAvatar";

/** Picture upload for one player (own picture or, for admins, anyone's). */
export function AvatarUpload({ playerId, name, avatar }: { playerId: number; name: string; avatar: string }) {
  const t = useT();
  const [busy, setBusy] = useState(false);
  const upload = (file: File | null) => {
    if (!file) return;
    setBusy(true);
    router.post("/avatars/upload/", { player: playerId, avatar: file, next: window.location.pathname }, { forceFormData: true, preserveScroll: true, onFinish: () => setBusy(false) });
  };
  return (
    <Paper withBorder p="md" mt="md">
      <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb="sm">{t("Picture")}</Text>
      <Group gap="md">
        <PlayerAvatar name={name} src={avatar} size={72} />
        <FileButton onChange={upload} accept="image/png,image/jpeg,image/webp,image/heic">
          {(props) => <Button {...props} loading={busy} leftSection={<IconPhotoUp size={16} />}>{t("Upload")}</Button>}
        </FileButton>
        {avatar && (
          <Button color="red" leftSection={<IconTrash size={16} />} onClick={() => router.post("/avatars/upload/", { player: playerId, remove: "1", next: window.location.pathname }, { preserveScroll: true })}>
            {t("Remove picture")}
          </Button>
        )}
      </Group>
      <Text size="xs" c="dimmed" mt="sm">{t("Shown in every round avatar of the portal (cropped to a square).")}</Text>
    </Paper>
  );
}
