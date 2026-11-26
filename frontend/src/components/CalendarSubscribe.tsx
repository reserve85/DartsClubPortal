import { ActionIcon, Badge, Button, Group, Modal, Stack, Text, Tooltip } from "@mantine/core";
import { IconCalendarPlus, IconCheck, IconCopy } from "@tabler/icons-react";
import { useState } from "react";
import { useT } from "../i18n";

export interface CalendarLink {
  team: string;
  own: boolean;
  url: string;
  webcal: string;
}

/** "Subscribe to calendar": the matchdays of a team in the phone's calendar app. */
export function CalendarSubscribe({ calendars, size = "sm" }: { calendars: CalendarLink[]; size?: "xs" | "sm" }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  if (!calendars.length) return null;
  const copy = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(url);
    } catch {
      window.prompt(t("Copy the address:"), url);
    }
  };
  return (
    <>
      <Button size={size} variant="light" leftSection={<IconCalendarPlus size={16} />} onClick={() => setOpen(true)}>
        {t("Subscribe to calendar")}
      </Button>
      <Modal opened={open} onClose={() => setOpen(false)} title={<Text fw={800}>{t("Subscribe to calendar")}</Text>} centered>
        <Text size="sm" c="dimmed" mb="md">
          {t("The matchdays appear in the calendar app of your phone and stay up to date by themselves (also moved or cancelled ones).")}
        </Text>
        <Stack gap="xs">
          {calendars.map((c) => (
            <Group key={c.url} justify="space-between" wrap="nowrap" gap="xs">
              <Group gap={6} wrap="nowrap" style={{ minWidth: 0 }}>
                <Text size="sm" fw={700} truncate>{c.team}</Text>
                {c.own && <Badge size="xs" color="dart">{t("my team")}</Badge>}
              </Group>
              <Group gap={6} wrap="nowrap">
                <Button size="xs" component="a" href={c.webcal}>{t("Subscribe")}</Button>
                <Tooltip label={copied === c.url ? t("Copied") : t("Copy link (e.g. for Google Calendar)")}>
                  <ActionIcon variant="light" size="lg" onClick={() => copy(c.url)} aria-label={t("Copy link")}>
                    {copied === c.url ? <IconCheck size={16} /> : <IconCopy size={16} />}
                  </ActionIcon>
                </Tooltip>
              </Group>
            </Group>
          ))}
        </Stack>
        <Text size="xs" c="dimmed" mt="md">
          {t("Google Calendar: Other calendars → From URL → paste the copied link.")}
        </Text>
      </Modal>
    </>
  );
}
