import { ActionIcon, Badge, Button, Group, Modal, SegmentedControl, Stack, Text, Tooltip } from "@mantine/core";
import { IconCalendarPlus, IconCheck, IconCopy } from "@tabler/icons-react";
import { useState } from "react";
import { useT } from "../i18n";

export interface CalendarLink {
  team: string;
  own: boolean;
  url: string;
  webcal: string;
  /** The same calendar without reminders. */
  urlPlain: string;
  webcalPlain: string;
  /** Reminders before the start, in minutes (club setting). */
  reminders: number[];
}

/** "Subscribe to calendar": the matchdays of a team in the phone's calendar app. */
export function CalendarSubscribe({ calendars, size = "sm" }: { calendars: CalendarLink[]; size?: "xs" | "sm" }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const reminders = calendars[0]?.reminders ?? [];
  const [withReminders, setWithReminders] = useState(reminders.length > 0);
  if (!calendars.length) return null;
  const copy = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(url);
    } catch {
      window.prompt(t("Copy the address:"), url);
    }
  };
  const duration = (m: number) => {
    const h = Math.floor(m / 60);
    const rest = m % 60;
    if (h && rest) return t("%(h)s h %(m)s min", { h, m: rest });
    return h ? t("%(n)s h", { n: h }) : t("%(n)s min", { n: m });
  };
  const when = reminders.map(duration).join(", ");
  return (
    <>
      <Button size={size} color="gray" leftSection={<IconCalendarPlus size={16} />} onClick={() => setOpen(true)}>
        {t("Subscribe to calendar")}
      </Button>
      <Modal opened={open} onClose={() => setOpen(false)} title={<Text fw={800}>{t("Subscribe to calendar")}</Text>} centered>
        <Text size="sm" c="dimmed" mb="md">
          {t("The matchdays appear in the calendar app of your phone and stay up to date by themselves (also moved or cancelled ones).")}
        </Text>
        {reminders.length > 0 && (
          <Stack gap={4} mb="md">
            <SegmentedControl
              fullWidth
              value={withReminders ? "with" : "without"}
              onChange={(v) => setWithReminders(v === "with")}
              data={[
                { value: "with", label: t("With reminders") },
                { value: "without", label: t("Without reminders") },
              ]}
            />
            <Text size="xs" c="dimmed">
              {withReminders
                ? t("Reminder %(when)s before the start (iPhone, Outlook; Google Calendar uses its own reminders).", { when })
                : t("No reminders - only the matchdays.")}
            </Text>
          </Stack>
        )}
        <Stack gap="xs">
          {calendars.map((c) => {
            const url = withReminders ? c.url : c.urlPlain;
            const webcal = withReminders ? c.webcal : c.webcalPlain;
            return (
              <Group key={c.url} justify="space-between" wrap="nowrap" gap="xs">
                <Group gap={6} wrap="nowrap" style={{ minWidth: 0 }}>
                  <Text size="sm" fw={700} truncate>{c.team}</Text>
                  {c.own && <Badge size="xs" color="brand">{t("my team")}</Badge>}
                </Group>
                <Group gap={6} wrap="nowrap">
                  <Button size="xs" component="a" href={webcal}>{t("Subscribe")}</Button>
                  <Tooltip label={copied === url ? t("Copied") : t("Copy link (e.g. for Google Calendar)")}>
                    <ActionIcon variant="light" size="lg" onClick={() => copy(url)} aria-label={t("Copy link")}>
                      {copied === url ? <IconCheck size={16} /> : <IconCopy size={16} />}
                    </ActionIcon>
                  </Tooltip>
                </Group>
              </Group>
            );
          })}
        </Stack>
        <Text size="xs" c="dimmed" mt="md">
          {t("Google Calendar: Other calendars → From URL → paste the copied link.")}
        </Text>
      </Modal>
    </>
  );
}
