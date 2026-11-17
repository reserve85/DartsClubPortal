import { router } from "@inertiajs/react";
import { Alert, Button, Group, Modal, Paper, PasswordInput, Stack, Text } from "@mantine/core";
import { IconAlertTriangle, IconKey } from "@tabler/icons-react";
import { useState } from "react";
import { useT } from "../i18n";

export interface PasswordSet {
  url: string;
  name: string;
  club: boolean;
}

/** Portal admins: give another account a new password, after a confirmation step. */
export function PasswordSetCard({ data }: { data: PasswordSet }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [password1, setPassword1] = useState("");
  const [password2, setPassword2] = useState("");
  const [busy, setBusy] = useState(false);
  const mismatch = password2 !== "" && password1 !== password2;
  const ready = password1 !== "" && password1 === password2;

  const close = () => {
    setOpen(false);
    setConfirming(false);
    setPassword1("");
    setPassword2("");
  };
  const submit = () => {
    setBusy(true);
    router.post(data.url, { password1, password2 }, { preserveScroll: true, onFinish: () => { setBusy(false); close(); } });
  };

  return (
    <Paper withBorder p="md">
      <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb="sm">{t("Password")}</Text>
      <Stack gap="xs" align="flex-start">
        <Text size="sm" c="dimmed">
          {data.club
            ? t("The club account has no e-mail for a reset: only portal admins set its password here.")
            : t("For a member who cannot reset the password by e-mail.")}
        </Text>
        <Button leftSection={<IconKey size={16} />} onClick={() => setOpen(true)}>{t("Set password")}</Button>
      </Stack>
      <Modal opened={open} onClose={close} title={<Text fw={800}>{t("Set password for %(name)s", { name: data.name })}</Text>} centered>
        {!confirming ? (
          <Stack gap="sm">
            <PasswordInput label={t("New password")} value={password1} onChange={(e) => setPassword1(e.currentTarget.value)} autoComplete="new-password" data-autofocus />
            <PasswordInput label={t("Repeat new password")} value={password2} onChange={(e) => setPassword2(e.currentTarget.value)} autoComplete="new-password" error={mismatch ? t("The two password fields didn't match.") : undefined} />
            <Group gap="xs" justify="flex-end">
              <Button color="gray" onClick={close}>{t("Cancel")}</Button>
              <Button disabled={!ready} onClick={() => setConfirming(true)}>{t("Continue")}</Button>
            </Group>
          </Stack>
        ) : (
          <Stack gap="sm">
            <Alert color="orange" variant="light" icon={<IconAlertTriangle size={18} />}>
              <Text size="sm">
                {data.club
                  ? t("Really set a new password for the club account? The tablet is signed out and every printed QR code stops working: print the poster again afterwards.")
                  : t("Really set a new password for %(name)s? The old password stops working and every device of this account is signed out. Tell the person the new password yourself.", { name: data.name })}
              </Text>
            </Alert>
            <Group gap="xs" justify="flex-end">
              <Button color="gray" onClick={() => setConfirming(false)}>{t("Back")}</Button>
              <Button color="red" loading={busy} onClick={submit}>{t("Set password")}</Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </Paper>
  );
}
