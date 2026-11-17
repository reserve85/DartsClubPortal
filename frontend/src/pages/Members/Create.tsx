import { Head, Link, useForm } from "@inertiajs/react";
import { Alert, Button, Group, NumberInput, Paper, Select, Stack, Switch, Text, TextInput } from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { IconAlertTriangle, IconUserPlus } from "@tabler/icons-react";
import dayjs from "dayjs";
import { PageHeader } from "../../components/ui";
import { useT } from "../../i18n";

type Choice = { value: string; label: string };
interface Props {
  season: string;
  teams: Choice[];
  defaultTeam: string;
  captainTeam: string | null;
  canElo: boolean;
  canInvite: boolean;
  languages: Choice[];
  defaults: { startElo: number | null; entryDate: string; language: string };
  today: string;
  backUrl: string;
  errors: Record<string, string>;
}

/** New member: name, team of the season, Elo start and invitation in one form. */
export default function MemberCreate({ season, teams, defaultTeam, captainTeam, canElo, canInvite, languages, defaults, today, backUrl, errors }: Props) {
  const t = useT();
  const form = useForm({
    name: "",
    team: defaultTeam,
    elo: canElo,
    start_elo: defaults.startElo ?? 1200,
    entry_date: defaults.entryDate,
    email: "",
    language: defaults.language,
  });
  const d = form.data;
  return (
    <>
      <Head title={t("New member")} />
      <PageHeader title={t("New member")} subtitle={t("One form for the person, team, Elo ranking and login.")} left={<IconUserPlus size={40} stroke={1.5} />} />
      <Paper withBorder p={{ base: "md", sm: "lg" }} maw={640}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            form.post("/players/create/", { preserveScroll: "errors" });
          }}
        >
          <Stack gap="md">
            {errors.form && <Alert color="red" icon={<IconAlertTriangle />}>{errors.form}</Alert>}
            <TextInput label={t("Name")} required value={d.name} onChange={(e) => form.setData("name", e.currentTarget.value)} error={errors.name} maxLength={120} data-autofocus />

            {captainTeam ? (
              <Text size="sm">{t("Team")}: <b>{captainTeam}</b>{season && <Text span c="dimmed"> · {season}</Text>}</Text>
            ) : (
              teams.length > 0 && (
                <Select
                  label={season ? `${t("Team")} · ${season}` : t("Team")}
                  description={t("Optional. More teams can be added on the member page.")}
                  data={[{ value: "", label: t("— no team —") }, ...teams]}
                  value={d.team}
                  onChange={(v) => form.setData("team", v ?? "")}
                  error={errors.team}
                  allowDeselect={false}
                />
              )
            )}

            {canElo && (
              <Paper withBorder p="sm" radius="md">
                <Switch
                  label={<Text fw={600}>🎯 {t("Plays in the Elo ranking")}</Text>}
                  checked={d.elo}
                  onChange={(e) => form.setData("elo", e.currentTarget.checked)}
                />
                {d.elo && (
                  <Group grow mt="sm" align="flex-start">
                    <NumberInput
                      label={t("Start Elo")}
                      min={100}
                      max={4000}
                      allowDecimal={false}
                      clampBehavior="strict"
                      value={d.start_elo}
                      onChange={(v) => form.setData("start_elo", Number(v) || 0)}
                      error={errors.start_elo}
                    />
                    <DatePickerInput
                      label={t("Entry date")}
                      value={d.entry_date}
                      maxDate={today}
                      onChange={(v) => form.setData("entry_date", v ? dayjs(v).format("YYYY-MM-DD") : d.entry_date)}
                      error={errors.entry_date}
                    />
                  </Group>
                )}
              </Paper>
            )}

            {canInvite && (
              <Paper withBorder p="sm" radius="md">
                <Text fw={600}>✉️ {t("Invite to the portal")}</Text>
                <Text size="xs" c="dimmed">{t("Optional: with an e-mail address the member gets an invitation; the account is linked automatically.")}</Text>
                <Group grow mt="sm" align="flex-start">
                  <TextInput type="email" label={t("E-mail address")} placeholder={t("optional")} value={d.email} onChange={(e) => form.setData("email", e.currentTarget.value)} error={errors.email} autoComplete="off" />
                  {d.email.trim() !== "" && (
                    <Select label={t("Language")} data={languages} value={d.language} onChange={(v) => form.setData("language", v ?? defaults.language)} allowDeselect={false} />
                  )}
                </Group>
              </Paper>
            )}

            <Group>
              <Button type="submit" loading={form.processing} leftSection={<IconUserPlus size={18} />}>{t("Add member")}</Button>
              <Button color="gray" component={Link} href={backUrl}>{t("Cancel")}</Button>
            </Group>
          </Stack>
        </form>
      </Paper>
    </>
  );
}
