import { Head, Link, router, useForm, usePage } from "@inertiajs/react";
import { Alert, Anchor, Button, Grid, Group, type MantineColorScheme, Paper, PasswordInput, SegmentedControl, Select, Stack, Switch, Text, TextInput, useMantineColorScheme } from "@mantine/core";
import { TimeInput } from "@mantine/dates";
import { IconAlertTriangle, IconInfoCircle, IconKey, IconMail, IconMailForward } from "@tabler/icons-react";
import { type KeyboardEvent, useEffect, useState } from "react";
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
  email: string;
  pendingEmail: string;
  emailUrl: string;
  /** Club account: password and e-mail are managed by a portal admin. */
  managed?: boolean;
  rightsUrl: string;
  errors: Record<string, string>;
  emailErrors: Record<string, string>;
}

const on = (v: unknown) => v === true || v === "True" || v === "true";

export default function Settings({ values, fields, choices, player, passwordUrl, email, pendingEmail, emailUrl, managed = false, rightsUrl, errors, emailErrors }: Props) {
  const t = useT();
  const { auth } = usePage<SharedProps>().props;
  const { setColorScheme } = useMantineColorScheme();
  const has = (f: string) => fields.includes(f);
  const form = useForm({
    full_name: String(values.full_name ?? ""),
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
  const frequency = (each: string, daily: boolean, onChange: (daily: boolean) => void) => (
    <SegmentedControl
      ml={54}
      data={[
        { value: "each", label: each },
        { value: "daily", label: t("Once a day") },
      ]}
      value={daily ? "daily" : "each"}
      onChange={(v) => onChange(v === "daily")}
    />
  );
  const penaltyOn = d.penalty_notify_mode !== "off";
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
                  {has("full_name") && (
                    <TextInput
                      label={t("Name")}
                      description={t("Only shown for accounts without a linked player (e.g. a club account).")}
                      value={d.full_name}
                      onChange={(e) => form.setData("full_name", e.currentTarget.value)}
                      error={errors.full_name}
                      maxLength={150}
                      autoComplete="name"
                    />
                  )}
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
                  {has("elo_match_digest") && d.elo_match_notify &&
                    frequency(t("Each match"), d.elo_match_digest, (daily) => form.setData("elo_match_digest", daily))}
                  {mail("elo_monthly_summary", `🎯 ${t("Monthly Elo summary")}`, t("On the 1st of each month: your position and Elo change, the highlights and the complete table with every player's movement."))}
                  {has("penalty_notify_mode") && (
                    <Switch
                      checked={penaltyOn}
                      onChange={(e) => form.setData("penalty_notify_mode", e.currentTarget.checked ? "immediate" : "off")}
                      label={<Text fw={600}>💶 {t("New penalties")}</Text>}
                      description={t("When a penalty is assigned to you. Several penalties entered in a row always arrive as ONE e-mail.")}
                    />
                  )}
                  {has("penalty_notify_mode") && penaltyOn &&
                    frequency(t("Each penalty"), d.penalty_notify_mode === "daily", (daily) =>
                      form.setData("penalty_notify_mode", daily ? "daily" : "immediate"),
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
            <Stack gap="md">
              <AccountCard email={email} pendingEmail={pendingEmail} emailUrl={emailUrl} passwordUrl={passwordUrl} managed={managed} rightsUrl={rightsUrl} player={player?.name ?? ""} errors={emailErrors} />
              {player && <AvatarUpload playerId={player.id} name={player.name} avatar={player.avatar} />}
            </Stack>
          </Grid.Col>
        </Grid>
      </form>
    </>
  );
}

/** Login address (change with confirmation link), password, linked player, rights. */
function AccountCard({ email, pendingEmail, emailUrl, passwordUrl, managed, rightsUrl, player, errors }: { email: string; pendingEmail: string; emailUrl: string; passwordUrl: string; managed: boolean; rightsUrl: string; player: string; errors: Record<string, string> }) {
  const t = useT();
  const [editing, setEditing] = useState(false);
  const form = useForm({ email: "", password: "" });
  useEffect(() => {
    if (errors.email || errors.password) setEditing(true);
  }, [errors]);
  const submit = () =>
    form.post(emailUrl, {
      preserveScroll: true,
      preserveState: true,
      onSuccess: (page) => {
        const failed = (page.props as { emailErrors?: Record<string, string> }).emailErrors ?? {};
        if (!Object.keys(failed).length) {
          form.reset();
          setEditing(false);
        } else form.setData("password", "");
      },
    });
  // The card sits inside the settings <form>: Enter must not submit that one.
  const enter = (e: KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      submit();
    }
  };
  return (
    <Paper withBorder p="md">
      <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb="sm">{t("Account")}</Text>
      <Stack gap="md">
        <div>
          <Text size="sm" fw={600}>{t("E-mail address")}</Text>
          <Text size="sm" c="dimmed" style={{ wordBreak: "break-all" }}>{email}</Text>
          {pendingEmail && (
            <Alert mt="xs" color="yellow" variant="light" icon={<IconMailForward size={18} />}>
              <Text size="sm">{t("Waiting for confirmation: %(email)s", { email: pendingEmail })}</Text>
              <Button mt={6} size="compact-sm" color="gray" onClick={() => router.post(emailUrl, { action: "cancel" }, { preserveScroll: true })}>
                {t("Withdraw change")}
              </Button>
            </Alert>
          )}
        </div>
        {managed ? (
          <Alert color="blue" variant="light" icon={<IconInfoCircle size={18} />}>
            <Text size="sm">{t("This is the club account: a portal admin manages its password and e-mail address.")}</Text>
          </Alert>
        ) : editing ? (
          <Stack gap="xs">
            <TextInput type="email" label={t("New e-mail address")} value={form.data.email} onChange={(e) => form.setData("email", e.currentTarget.value)} onKeyDown={enter} error={errors.email} autoComplete="email" data-autofocus />
            <PasswordInput label={t("Current password")} value={form.data.password} onChange={(e) => form.setData("password", e.currentTarget.value)} onKeyDown={enter} error={errors.password} autoComplete="current-password" />
            <Text size="xs" c="dimmed">{t("The new address gets a confirmation link. Until you confirm it, your current address stays in use.")}</Text>
            <Group gap="xs">
              <Button onClick={submit} loading={form.processing}>{t("Change e-mail")}</Button>
              <Button color="gray" onClick={() => { form.reset(); setEditing(false); }}>{t("Cancel")}</Button>
            </Group>
          </Stack>
        ) : (
          <Group gap="xs">
            <Button leftSection={<IconMail size={16} />} onClick={() => setEditing(true)}>{t("Change e-mail")}</Button>
            <Button component="a" href={passwordUrl} leftSection={<IconKey size={16} />}>{t("Change password")}</Button>
          </Group>
        )}
        <div>
          <Text size="sm" fw={600}>{t("Linked player")}</Text>
          <Text size="sm" c="dimmed">{player || t("No player linked.")}</Text>
          <Text size="xs" c="dimmed">{t("The admins link players and change their names.")}</Text>
        </div>
        <Anchor component={Link} href={rightsUrl} size="sm">
          <Group gap={6} wrap="nowrap"><IconInfoCircle size={16} />{t("Who may do what?")}</Group>
        </Anchor>
      </Stack>
    </Paper>
  );
}
