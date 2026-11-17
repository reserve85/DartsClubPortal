import { Head, Link, router } from "@inertiajs/react";
import { Alert, Anchor, Badge, Box, Button, Checkbox, Chip, Group, Paper, Select, Stack, Text, Textarea, TextInput } from "@mantine/core";
import { modals } from "@mantine/modals";
import { IconChevronRight, IconMailForward, IconSearch, IconSettings, IconUserCheck, IconUserCog, IconUserPlus, IconUsersGroup } from "@tabler/icons-react";
import { type KeyboardEvent, useState } from "react";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { EmptyState, PageHeader } from "../../components/ui";
import { useT } from "../../i18n";

type Choice = { value: string; label: string };
interface Member {
  id: number;
  name: string;
  active: boolean;
  avatar: string;
  teams: string[];
  elo: { current: number; disabled: boolean } | null;
  account: { state: "linked" | "invited" | "none"; email: string; active: boolean };
  editUrl: string;
}
interface Props {
  members: Member[];
  season: string;
  eloEnabled: boolean;
  penaltyEnabled: boolean;
  can: { elo: boolean; invite: boolean };
  teams: Choice[];
  defaultTeam: string;
  languages: Choice[];
  language: string;
  pendingApprovals: number;
  accountsWithoutPlayer: number;
  urls: { create: string; quickAdd: string; users: string | null; approvals: string | null; list: string };
}

type Filter = "all" | "noAccount" | "invited" | "account" | "noElo" | "inactive";

export default function MemberList(p: Props) {
  const t = useT();
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const needle = q.trim().toLowerCase();
  const active = p.members.filter((m) => m.active);
  // Inactive members are always listed (dimmed); "Inactive" narrows to them.
  const tests: Record<Filter, (m: Member) => boolean> = {
    all: () => true,
    noAccount: (m) => m.account.state === "none",
    invited: (m) => m.account.state === "invited",
    account: (m) => m.account.state === "linked",
    noElo: (m) => !m.elo,
    inactive: (m) => !m.active,
  };
  const count = (f: Filter) => p.members.filter(tests[f]).length;
  const shown = p.members.filter(
    (m) => tests[filter](m) && (!needle || `${m.name} ${m.account.email} ${m.teams.join(" ")}`.toLowerCase().includes(needle)),
  );
  const chips: [Filter, string][] = [
    ["all", t("All")],
    ["noAccount", t("Without account")],
    ["invited", t("Invited")],
    ["account", t("With account")],
    ...(p.eloEnabled ? ([["noElo", t("Without Elo")]] as [Filter, string][]) : []),
    ["inactive", t("Inactive")],
  ];
  return (
    <>
      <Head title={t("Members")} />
      <PageHeader
        title={t("Members")}
        subtitle={[t("%(n)s active", { n: active.length }), p.season].filter(Boolean).join(" · ")}
        left={<IconUsersGroup size={40} stroke={1.5} />}
        actions={p.urls.users && <Button component={Link} href={p.urls.users} color="gray" leftSection={<IconUserCog size={18} />}>{t("Accounts & rights")}</Button>}
      >
        <QuickAdd {...p} />
      </PageHeader>

      {p.pendingApprovals > 0 && p.urls.approvals && (
        <Alert color="orange" icon={<IconUserCheck />} mb="md" title={t("%(n)s registration(s) waiting for approval", { n: p.pendingApprovals })}>
          <Button size="xs" color="orange" component={Link} href={p.urls.approvals}>{t("Review now")}</Button>
        </Alert>
      )}

      <Stack gap="sm" mb="md">
        <TextInput placeholder={t("Search")} leftSection={<IconSearch size={16} />} value={q} onChange={(e) => setQ(e.currentTarget.value)} />
        <Chip.Group value={filter} onChange={(v) => setFilter(v as Filter)}>
          <Group gap={6}>
            {chips.map(([key, label]) => (
              <Chip key={key} value={key} size="sm" variant="filled">{label} · {count(key)}</Chip>
            ))}
          </Group>
        </Chip.Group>
      </Stack>

      {shown.length === 0 ? (
        <EmptyState>{needle ? t("Nothing found.") : t("No members yet.")}</EmptyState>
      ) : (
        <Stack gap="xs">
          {shown.map((m) => <Row key={m.id} m={m} {...p} />)}
        </Stack>
      )}

      {p.accountsWithoutPlayer > 0 && p.urls.users && (
        <Text size="sm" c="dimmed" mt="md">
          {t("%(n)s account(s) without a player (e.g. club account):", { n: p.accountsWithoutPlayer })}{" "}
          <Anchor component={Link} href={p.urls.users}>{t("Accounts & rights")}</Anchor>
        </Text>
      )}
    </>
  );
}

/** Type names, press Enter: one member per line with the usual defaults. */
function QuickAdd({ can, teams, defaultTeam, urls }: Props) {
  const t = useT();
  const [names, setNames] = useState("");
  const [team, setTeam] = useState(defaultTeam);
  const [elo, setElo] = useState(can.elo);
  const [busy, setBusy] = useState(false);
  const submit = () =>
    names.trim() &&
    router.post(urls.quickAdd, { names, team, elo }, {
      preserveScroll: true,
      onStart: () => setBusy(true),
      onFinish: () => setBusy(false),
      onSuccess: () => setNames(""),
    });
  const enter = (e: KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };
  return (
    <Paper withBorder p="sm" radius="md">
      <Stack gap="xs">
        <Textarea
          label={t("Add members quickly")}
          description={t("Name + Enter. Several at once: one name per line (Shift+Enter).")}
          placeholder={t("First and last name")}
          autosize
          minRows={1}
          maxRows={8}
          value={names}
          onChange={(e) => setNames(e.currentTarget.value)}
          onKeyDown={enter}
        />
        <Group gap="sm" wrap="wrap" align="center">
          {teams.length > 1 && (
            <Select size="xs" w={200} data={[{ value: "", label: t("— no team —") }, ...teams]} value={team} onChange={(v) => setTeam(v ?? "")} allowDeselect={false} aria-label={t("Team")} />
          )}
          {teams.length === 1 && <Badge color="yellow" variant="light">{teams[0].label}</Badge>}
          {can.elo && <Checkbox size="sm" label={t("Elo ranking")} checked={elo} onChange={(e) => setElo(e.currentTarget.checked)} />}
          <Group gap="xs" ml="auto">
            <Button size="sm" leftSection={<IconUserPlus size={16} />} onClick={submit} loading={busy} disabled={!names.trim()}>{t("Add")}</Button>
            <Button size="sm" variant="default" component={Link} href={urls.create} leftSection={<IconSettings size={16} />}>{t("More options")}</Button>
          </Group>
        </Group>
      </Stack>
    </Paper>
  );
}

function Row({ m, eloEnabled, penaltyEnabled, can, languages, language, urls }: Props & { m: Member }) {
  const t = useT();
  const back = { next: urls.list };
  const invite = () =>
    modals.open({
      modalId: "invite",
      title: <Text fw={800}>{t("Invite %(name)s", { name: m.name })}</Text>,
      // Rendered outside the Inertia page: texts are passed in, no useT() there.
      children: (
        <InviteForm
          url={m.editUrl}
          next={urls.list}
          languages={languages}
          language={language}
          text={{
            email: t("E-mail address"),
            language: t("Language"),
            hint: t("The account is linked to this member when the invitation is accepted."),
            cancel: t("Cancel"),
            send: t("Send invitation"),
          }}
        />
      ),
    });
  return (
    <Paper withBorder p="sm" radius="md" style={{ opacity: m.active ? 1 : 0.6 }}>
      <Group wrap="nowrap" gap="sm" align="center">
        <Link href={m.editUrl} style={{ display: "contents", color: "inherit", textDecoration: "none" }}>
          <PlayerAvatar name={m.name} src={m.avatar} size={40} muted={!m.active} />
          <Box style={{ minWidth: 0, flex: 1 }}>
            <Text fw={800} truncate>{m.name}</Text>
            {m.account.email && <Text size="xs" c="dimmed" truncate>{m.account.email}</Text>}
            <Group gap={6} mt={6}>
              {m.account.state === "linked" && <Badge color="teal" variant="light">{t("Account")}</Badge>}
              {m.account.state === "invited" && <Badge color="cyan" variant="light">{t("invited")}</Badge>}
              {m.account.state === "none" && <Badge color="gray" variant="outline">{t("no account")}</Badge>}
              {eloEnabled && m.elo && <Badge color={m.elo.disabled ? "gray" : "brand"} variant="light" className="num">Elo {m.elo.current}</Badge>}
              {penaltyEnabled && m.teams.map((team) => <Badge key={team} color="yellow" variant="light">{team}</Badge>)}
              {!m.active && <Badge color="gray">{t("inactive")}</Badge>}
            </Group>
          </Box>
        </Link>
        <Stack gap={6} align="flex-end" style={{ flexShrink: 0 }}>
          {m.active && can.invite && m.account.state === "none" && (
            <Button size="compact-sm" leftSection={<IconMailForward size={14} />} onClick={invite}>{t("Invite")}</Button>
          )}
          {m.active && can.elo && eloEnabled && !m.elo && (
            <Button size="compact-sm" color="dart" variant="light" onClick={() => router.post(m.editUrl, { section: "elo", action: "add", ...back }, { preserveScroll: true })}>
              + Elo
            </Button>
          )}
          <Link href={m.editUrl} aria-label={m.name}><IconChevronRight size={18} style={{ opacity: 0.5 }} /></Link>
        </Stack>
      </Group>
    </Paper>
  );
}

function InviteForm({ url, next, languages, language, text }: { url: string; next: string; languages: Choice[]; language: string; text: Record<"email" | "language" | "hint" | "cancel" | "send", string> }) {
  const [email, setEmail] = useState("");
  const [lang, setLang] = useState(language);
  const [busy, setBusy] = useState(false);
  const send = () =>
    router.post(url, { section: "account", action: "invite", email, language: lang, next }, {
      preserveScroll: true,
      onStart: () => setBusy(true),
      onFinish: () => setBusy(false),
      onSuccess: () => modals.close("invite"),
    });
  return (
    <Stack gap="sm">
      <TextInput
        type="email"
        label={text.email}
        value={email}
        onChange={(e) => setEmail(e.currentTarget.value)}
        onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); send(); } }}
        data-autofocus
        autoComplete="off"
      />
      <Select label={text.language} data={languages} value={lang} onChange={(v) => setLang(v ?? language)} allowDeselect={false} />
      <Text size="xs" c="dimmed">{text.hint}</Text>
      <Group justify="flex-end">
        <Button color="gray" onClick={() => modals.close("invite")}>{text.cancel}</Button>
        <Button leftSection={<IconMailForward size={16} />} onClick={send} loading={busy} disabled={!email.includes("@")}>{text.send}</Button>
      </Group>
    </Stack>
  );
}
