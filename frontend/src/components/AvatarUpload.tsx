import { router } from "@inertiajs/react";
import { Button, FileButton, Group, Paper, Text } from "@mantine/core";
import { IconCrop, IconPhotoUp, IconTrash } from "@tabler/icons-react";
import { useRef, useState } from "react";
import { useT } from "../i18n";
import { AvatarCropDialog } from "./AvatarCrop";
import { PlayerAvatar } from "./PlayerAvatar";

/** Picture of one player (own picture or, for admins, anyone's): choose, crop round, upload. */
export function AvatarUpload({ playerId, name, avatar }: { playerId: number; name: string; avatar: string }) {
  const t = useT();
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const resetRef = useRef<() => void>(null);
  const choose = (f: File | null) => {
    setFile(f);
    resetRef.current?.(); // the same file can be chosen again
  };
  const upload = (cropped: File) => {
    setFile(null);
    setBusy(true);
    router.post("/avatars/upload/", { player: playerId, avatar: cropped, next: window.location.pathname }, {
      forceFormData: true,
      preserveScroll: true,
      onFinish: () => setBusy(false),
    });
  };
  // Adjust the section of the current picture without choosing a new file.
  const recrop = async () => {
    const blob = await fetch(avatar, { credentials: "same-origin" }).then((r) => r.blob());
    setFile(new File([blob], "avatar.jpg", { type: blob.type || "image/jpeg" }));
  };
  return (
    <Paper withBorder p="md" mt="md">
      <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb="sm">{t("Picture")}</Text>
      <Group gap="md">
        <PlayerAvatar name={name} src={avatar} size={72} />
        <FileButton resetRef={resetRef} onChange={choose} accept="image/png,image/jpeg,image/webp,image/heic,image/heif">
          {(props) => <Button {...props} loading={busy} leftSection={<IconPhotoUp size={16} />}>{avatar ? t("New picture") : t("Upload")}</Button>}
        </FileButton>
        {avatar && (
          <Button variant="default" leftSection={<IconCrop size={16} />} onClick={recrop}>{t("Change section")}</Button>
        )}
        {avatar && (
          <Button color="red" variant="light" leftSection={<IconTrash size={16} />} onClick={() => router.post("/avatars/upload/", { player: playerId, remove: "1", next: window.location.pathname }, { preserveScroll: true })}>
            {t("Remove picture")}
          </Button>
        )}
      </Group>
      <Text size="xs" c="dimmed" mt="sm">{t("Choose a picture, then move and zoom it inside the circle.")}</Text>
      <AvatarCropDialog file={file} onCancel={() => setFile(null)} onDone={upload} />
    </Paper>
  );
}
