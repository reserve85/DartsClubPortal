import { Head, useForm, usePage } from "@inertiajs/react";
import { Alert, Button, Grid, type MantineColorScheme, Paper, SegmentedControl, Select, Stack, Switch, Text, useMantineColorScheme } from "@mantine/core";
import { TimeInput } from "@mantine/dates";
import { IconAlertTriangle, IconKey } from "@tabler/icons-react";
import { AvatarUpload } from "../../components/AvatarUpload";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { PageHeader } from "../../components/ui";
import { useT } from "../../i18n";
import type { SharedProps } from "../../types";

type Choice = { value: string; label: string };
interface Props {
  values: Record<string, unknown>;
  fields: string[];
  choices: Record<string, Choice[]>;
  player: { id: number; name: string; avatar: string } | null;
  passwordUrl: string;
  errors: Record<string, string>;
}

const on = (v: unknown) => v === true || v === "True" || v === "true";

export default function Settings({ values, fields, choices, player, passwordUrl, errors }: Props) {
  const t = useT();
  const { auth } = usePage<SharedProps>().props;
  const { setColorScheme } = useMantineColorScheme();
  const has = (f: string) => fields.includes(f);
  const form = useForm({
    preferred_language: String(values.preferred_language ?? "de"),
    preferred_theme: String(values.preferred_theme ?? "auto"),
    start_page: String(values.start_page ?? "auto"),
    penalty_notify_mode: String(values.penalty_notify_mode ?? "daily"),
    penalty_notify_time: String(values.penalty_notify_time ?? "08:00"),
    repayment_notify: on(values.repayment_notify),
    club_news_optin: on(values.club_news_optin),
    elo_match_notify: on(values.elo_match_notify),
    elo_match_digest: on(values.elo_match_digest),
    elo_monthly_summary: on(values.elo_monthly_summary),
  });
  const d = form.data;
  const mail = (key: "repayment_notify" | "club_news_optin" | "elo_match_notify" | "elo_monthly_summary", label: string, help: string) =>
    has(key) && (
      <Switch
        checked={d[key]}
        onChange={(e) => form.setData(key, e.currentTarget.checked)}
        label={<Text fw={600}>{label}</Text>}
        description={help}
      />
    );
  return (
    <>
      <Head title={t("Settings")} />
      <PageHeader
        left={<PlayerAvatar name={auth.user?.name ?? "?"} src={auth.user?.avatar} size={56} />}
        title={t("Settings")}
        subtitle={`${auth.user?.email}${player ? ` · ${player.name}` : ""}`}
      />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const languageChanged = d.preferred_language !== String(values.preferred_language);
          form.post("/accounts/settings/", {
            preserveScroll: true,
            onSuccess: () => {
              setColorScheme(d.preferred_theme as MantineColorScheme);
              if (languageChanged) window.location.reload(); // dates and texts in the new language
            },
          });
        }}
      >
        <Grid gap="md">
          <Grid.Col span={{ base: 12, md: 7 }}>
            <Stack gap="md">
              {errors.form && <Alert color="red" icon={<IconAlertTriangle />}>{errors.form}</Alert>}
              <Paper withBorder p="md">
                <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb="sm">{t("Display")}</Text>
                <Stack>
                  <Select label={t("Language")} data={choices.preferred_language} value={d.preferred_language} onChange={(v) => form.setData("preferred_language", v ?? "de")} />
                  <div>
                    <Text size="sm" fw={500} mb={4}>{t("Colour scheme")}</Text>
                    <SegmentedControl fullWidth data={choices.preferred_theme} value={d.preferred_theme} onChange={(v) => form.setData("preferred_theme", v)} />
                  </div>
                  <Select label={t("start page")} description={t("Where you land after login.")} data={choices.start_page} value={d.start_page} onChange={(v) => form.setData("start_page", v ?? "auto")} />
                </Stack>
              </Paper>
              <Paper withBorder p="md">
                <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb="xs">{t("E-mail notifications")}</Text>
                <Text size="sm" c="dimmed" mb="md">{t("Invitations, approval decisions, password and verification mails are always sent. Every other mail has an unsubscribe link.")}</Text>
                <Stack gap="md">
                  {mail("elo_match_notify", `🎯 ${t("Elo match results")}`, t("When a match of yours is entered, corrected or deleted."))}
                  {has("elo_match_digest") && d.elo_match_notify && (
                    <SegmentedControl
                      ml={54}
                      data={[
                        { value: "now", label: t("Each match") },
                        { value: "daily", label: t("Once a day") },
                      ]}
                      value={d.elo_match_digest ? "daily" : "now"}
                      onChange={(v) => form.setData("elo_match_digest", v === "daily")}
                    />
                  )}
                  {mail("elo_monthly_summary", `🎯 ${t("Monthly Elo summary")}`, t("On the 1st of each month: your position and Elo change, the highlights and the complete table with every player's movement."))}
                  {has("penalty_notify_mode") && (
                    <div>
                      <Text fw={600} size="sm" mb={4}>💶 {t("New penalties")}</Text>
                      <SegmentedControl fullWidth data={choices.penalty_notify_mode} value={d.penalty_notify_mode} onChange={(v) => form.setData("penalty_notify_mode", v)} />
                      <Text size="xs" c="dimmed" mt={4}>{t("Several penalties entered in a row always arrive as ONE e-mail.")}</Text>
                    </div>
                  )}
                  {has("penalty_notify_time") && ((has("penalty_notify_mode") && d.penalty_notify_mode === "daily") || (d.elo_match_notify && d.elo_match_digest)) && (
                    <TimeInput
                      label={t("Digest time")}
                      description={t("Daily summaries (penalties and Elo matches) arrive at this time.")}
                      value={d.penalty_notify_time}
                      onChange={(e) => form.setData("penalty_notify_time", e.currentTarget.value)}
                      error={errors.penalty_notify_time}
                      maw={260}
                    />
                  )}
                  {mail("repayment_notify", `💶 ${t("Payment confirmations")}`, t("One e-mail per recorded payment or payout — the confirmation for the money movement."))}
                  {mail("club_news_optin", `📣 ${t("Club news / round mails")}`, t("Round mails and information from your club."))}
                </Stack>
              </Paper>
              <Button type="submit" size="md" loading={form.processing} style={{ alignSelf: "flex-start" }}>{t("Save preferences")}</Button>
            </Stack>
          </Grid.Col>
          <Grid.Col span={{ base: 12, md: 5 }}>
            {player && <AvatarUpload playerId={player.id} name={player.name} avatar={player.avatar} />}
            <Paper withBorder p="md" mt="md">
              <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb="xs">{t("Change password")}</Text>
              <Text size="sm" c="dimmed" mb="sm">{t("Set a new password for your account.")}</Text>
              <Button component="a" href={passwordUrl} leftSection={<IconKey size={16} />}>{t("Change password")}</Button>
            </Paper>
          </Grid.Col>
        </Grid>
      </form>
    </>
  );
}
