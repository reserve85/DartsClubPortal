import { Head, Link, router } from "@inertiajs/react";
import { Alert, Badge, Button, Checkbox, Group, NumberInput, Paper, Select, SimpleGrid, Stack, Switch, Text, TextInput } from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { IconChartLine, IconEdit, IconLink, IconMailForward, IconUnlink, IconUser } from "@tabler/icons-react";
import dayjs from "dayjs";
import { type ReactNode, useEffect, useState } from "react";
import { confirmPost } from "../../components/elo";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { PageHeader, Section } from "../../components/ui";
import { useFormat, useT } from "../../i18n";

type Choice = { value: string; label: string };
interface EloProfile {
  current: number;
  start: number;
  entryDate: string;
  disabled: boolean;
  firstMatch: string | null;
  editUrl: string;
  statsUrl: string;
}
interface Props {
  player: { id: number; name: string; active: boolean; avatar: string; detailUrl: string };
  season: string;
  teams: { id: number; name: string; checked: boolean; editable: boolean }[];
  elo: { profile: EloProfile | null; defaults: { startElo: number; entryDate: string } } | null;
  account: {
    user: { email: string; active: boolean; lastLogin: string | null; editUrl: string } | null;
    invitation: { email: string; expires: string; manageUrl: string } | null;
    linkable: Choice[];
    languages: Choice[];
    language: string;
  } | null;
  url: string;
  backUrl: string;
  errors: Record<string, Record<string, string>>;
}

/** One member: basics, teams of the season, Elo ranking, login. */
export default function MemberEdit({ player, season, teams, elo, account, url, backUrl, errors }: Props) {
  const t = useT();
  const f = useFormat();
  const [busy, setBusy] = useState<string | null>(null);
  const post = (section: string, data: Record<string, unknown>) =>
    router.post(url, { section, ...data }, {
      preserveScroll: true,
      preserveState: true,
      onStart: () => setBusy(section),
      onFinish: () => setBusy(null),
    });
  const err = (section: string) => errors[section] ?? {};

  // Basics
  const [name, setName] = useState(player.name);
  const [active, setActive] = useState(player.active);
  useEffect(() => { setName(player.name); setActive(player.active); }, [player.name, player.active]);
  // Teams
  const [checked, setChecked] = useState<number[]>(teams.filter((x) => x.checked).map((x) => x.id));
  useEffect(() => setChecked(teams.filter((x) => x.checked).map((x) => x.id)), [teams]);
  const editableTeams = teams.some((x) => x.editable);

  return (
    <>
      <Head title={player.name} />
      <PageHeader
        title={player.name}
        subtitle={[t("Member"), !player.active ? t("inactive") : ""].filter(Boolean).join(" · ")}
        left={<PlayerAvatar name={player.name} src={player.avatar} size={52} muted={!player.active} />}
        actions={
          <>
            <Button component={Link} href={player.detailUrl} color="gray" leftSection={<IconUser size={16} />}>{t("Profile")}</Button>
            <Button component={Link} href={backUrl} color="gray">{t("Back")}</Button>
          </>
        }
      />

      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
        <Card title={t("Basics")}>
          <Stack gap="sm">
            <TextInput label={t("Name")} value={name} onChange={(e) => setName(e.currentTarget.value)} error={err("basics").name} maxLength={120} />
            <Group><Button onClick={() => post("basics", { name, active })} loading={busy === "basics"} disabled={name.trim() === player.name}>{t("Save name")}</Button></Group>
            <Switch
              label={t("Active")}
              description={t("Inactive members stay in the history but are hidden in new matchdays and lists.")}
              checked={active}
              onChange={(e) => {
                // Saved right away: one tap, no extra button.
                const on = e.currentTarget.checked;
                setActive(on);
                post("basics", { name: player.name, active: on });
              }}
            />
          </Stack>
        </Card>

        {teams.length > 0 && (
          <Card title={season ? `${t("Teams")} · ${season}` : t("Teams")}>
            <Stack gap="xs">
              {teams.map((team) => (
                <Checkbox
                  key={team.id}
                  label={team.name}
                  checked={checked.includes(team.id)}
                  disabled={!team.editable}
                  onChange={(e) => {
                    // Saved right away: one tap, no extra button.
                    const on = e.currentTarget.checked;
                    const next = on ? [...checked, team.id] : checked.filter((x) => x !== team.id);
                    setChecked(next);
                    post("teams", { teams: next });
                  }}
                />
              ))}
              {editableTeams && <Text size="xs" c="dimmed">{t("Changes are saved right away.")}</Text>}
            </Stack>
          </Card>
        )}

        {elo && <EloCard elo={elo} name={player.name} url={url} errors={err("elo")} busy={busy === "elo"} post={(d) => post("elo", d)} />}

        {account && <AccountCard account={account} name={player.name} url={url} errors={err("account")} busy={busy === "account"} post={(d) => post("account", d)} f={f} />}
      </SimpleGrid>
    </>
  );
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Section title={title}>
      <Paper withBorder p="md" radius="md">{children}</Paper>
    </Section>
  );
}

function EloCard({ elo, name, url, errors, busy, post }: { elo: NonNullable<Props["elo"]>; name: string; url: string; errors: Record<string, string>; busy: boolean; post: (d: Record<string, unknown>) => void }) {
  const t = useT();
  const f = useFormat();
  const p = elo.profile;
  const [start, setStart] = useState<number>(elo.defaults.startElo);
  const [entry, setEntry] = useState<string>(elo.defaults.entryDate);
  return (
    <Card title={t("Elo ranking")}>
      {errors.form && <Alert color="red" mb="sm">{errors.form}</Alert>}
      {p ? (
        <Stack gap="sm">
          <Group gap="xl">
            <div><Text size="xs" c="dimmed">{t("Current Elo")}</Text><Text fw={800} fz={24} className="num">{p.current}</Text></div>
            <div><Text size="xs" c="dimmed">{t("Start Elo")}</Text><Text fw={700} className="num">{p.start}</Text></div>
            <div><Text size="xs" c="dimmed">{t("Entry date")}</Text><Text fw={700}>{f.date(p.entryDate)}</Text></div>
          </Group>
          {p.disabled && <Badge color="gray" variant="filled">{t("disabled")}</Badge>}
          <Group gap="xs">
            <Button component={Link} href={p.editUrl} leftSection={<IconEdit size={16} />} color="yellow">{t("Edit")}</Button>
            <Button component={Link} href={p.statsUrl} color="gray" leftSection={<IconChartLine size={16} />}>{t("Statistics")}</Button>
            <Button
              color={p.disabled ? "teal" : "red"}
              variant="light"
              onClick={() =>
                p.disabled
                  ? post({ action: "toggle" })
                  : confirmPost({
                      title: t("Disable %(name)s?", { name }),
                      body: t("Stays in the ranking, cannot play new matches."),
                      confirm: t("Disable"),
                      cancel: t("Cancel"),
                      url,
                      data: { section: "elo", action: "toggle" },
                    })
              }
            >
              {p.disabled ? t("Enable again") : t("Disable")}
            </Button>
          </Group>
        </Stack>
      ) : (
        <Stack gap="sm">
          <Text size="sm" c="dimmed">{t("Not in the Elo ranking yet.")}</Text>
          <Group grow align="flex-start">
            <NumberInput label={t("Start Elo")} min={100} max={4000} allowDecimal={false} clampBehavior="strict" value={start} onChange={(v) => setStart(Number(v) || 0)} error={errors.start_elo} />
            <DatePickerInput label={t("Entry date")} value={entry} maxDate={dayjs().format("YYYY-MM-DD")} onChange={(v) => v && setEntry(dayjs(v).format("YYYY-MM-DD"))} error={errors.entry_date} />
          </Group>
          <Group><Button onClick={() => post({ action: "add", start_elo: start, entry_date: entry })} loading={busy}>🎯 {t("Add to the Elo ranking")}</Button></Group>
        </Stack>
      )}
    </Card>
  );
}

function AccountCard({ account, name, url, errors, busy, post, f }: { account: NonNullable<Props["account"]>; name: string; url: string; errors: Record<string, string>; busy: boolean; post: (d: Record<string, unknown>) => void; f: ReturnType<typeof useFormat> }) {
  const t = useT();
  const [email, setEmail] = useState("");
  const [language, setLanguage] = useState(account.language);
  const [user, setUser] = useState<string | null>(null);
  const { user: linked, invitation } = account;
  return (
    <Card title={t("Account")}>
      {linked ? (
        <Stack gap="sm">
          <div>
            <Text size="sm" fw={600} style={{ wordBreak: "break-all" }}>{linked.email}</Text>
            <Text size="xs" c="dimmed">{linked.lastLogin ? `${t("Last login")}: ${f.date(linked.lastLogin)}` : t("Never logged in")}</Text>
          </div>
          {!linked.active && <Badge color="gray">{t("inactive")}</Badge>}
          <Group gap="xs">
            <Button component={Link} href={linked.editUrl} color="yellow" leftSection={<IconEdit size={16} />}>{t("Rights & account")}</Button>
            <Button
              color="red"
              variant="light"
              leftSection={<IconUnlink size={16} />}
              onClick={() =>
                confirmPost({
                  title: t("Unlink the account?"),
                  body: t("%(email)s keeps the login but no longer belongs to %(name)s.", { email: linked.email, name }),
                  confirm: t("Unlink"),
                  cancel: t("Cancel"),
                  url,
                  data: { section: "account", action: "unlink" },
                })
              }
            >
              {t("Unlink")}
            </Button>
          </Group>
        </Stack>
      ) : invitation ? (
        <Stack gap="sm">
          <Alert color="cyan" variant="light" icon={<IconMailForward size={18} />}>
            <Text size="sm">{t("Invited: %(email)s", { email: invitation.email })}</Text>
            <Text size="xs" c="dimmed">{t("Valid until %(date)s", { date: f.date(invitation.expires) })}</Text>
          </Alert>
          <Group><Button component={Link} href={invitation.manageUrl} color="gray">{t("Manage invitations")}</Button></Group>
        </Stack>
      ) : (
        <Stack gap="md">
          <Text size="sm" c="dimmed">{t("No account yet. Invite the member or link an existing account.")}</Text>
          <Stack gap="xs">
            <Group grow align="flex-start">
              <TextInput type="email" label={t("E-mail address")} value={email} onChange={(e) => setEmail(e.currentTarget.value)} error={errors.email} autoComplete="off" />
              <Select label={t("Language")} data={account.languages} value={language} onChange={(v) => setLanguage(v ?? account.language)} allowDeselect={false} />
            </Group>
            <Group><Button leftSection={<IconMailForward size={16} />} onClick={() => post({ action: "invite", email, language })} loading={busy}>{t("Send invitation")}</Button></Group>
          </Stack>
          {account.linkable.length > 0 && (
            <Stack gap="xs">
              <Select
                label={t("Link an existing account")}
                placeholder={t("Choose an account")}
                data={account.linkable}
                value={user}
                onChange={setUser}
                searchable
                error={errors.user}
              />
              <Group><Button color="gray" leftSection={<IconLink size={16} />} disabled={!user} onClick={() => post({ action: "link", user })}>{t("Link")}</Button></Group>
            </Stack>
          )}
        </Stack>
      )}
    </Card>
  );
}
