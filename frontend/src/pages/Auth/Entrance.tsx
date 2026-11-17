import { Head, Link, router, useForm, usePage } from "@inertiajs/react";
import { Alert, Anchor, Box, Button, Center, Group, Image, Loader, Paper, SegmentedControl, Stack, Text, Title, useComputedColorScheme, useMantineColorScheme, type MantineColorScheme } from "@mantine/core";
import { IconAlertTriangle, IconCircleCheck, IconMailCheck } from "@tabler/icons-react";
import { useEffect, useState, type ReactNode } from "react";
import { CookieNotice } from "../../components/CookieNotice";
import { FormFields, initialData, type FieldDef } from "../../components/FormFields";
import AppLayout, { useFlashToasts } from "../../layout/AppLayout";
import { useFormat, useT } from "../../i18n";
import type { SharedProps } from "../../types";

type Kind =
  | "login" | "signup" | "password_reset" | "password_reset_done" | "password_reset_key"
  | "password_reset_key_done" | "email_confirm" | "verification_sent" | "logout"
  | "password_change" | "inactive" | "invite_accept" | "qr_login" | "unsubscribe";

interface Props {
  kind: Kind;
  fields: FieldDef[];
  errors: Record<string, string>;
  action: string;
  tokenFail?: boolean;
  confirmation?: { email: string; canConfirm: boolean; action: string } | null;
  invitation?: { email: string; role: string; team: string; player: string; expires: string; error: string | null };
  qr?: { postUrl: string; legacy: boolean };
  unsubscribe?: { valid: boolean; label: string; done: boolean };
}

function Brand() {
  const { site } = usePage<SharedProps>().props;
  const scheme = useComputedColorScheme("dark");
  const src = scheme === "dark" ? site.logo?.dark || site.logo?.light : site.logo?.light || site.logo?.dark;
  return (
    <Stack align="center" gap={8} mb="lg">
      {src ? (
        <Image src={src} h={84} w="auto" maw={220} fit="contain" alt={site.name} />
      ) : (
        <Box w={64} h={64} fz={34} style={{ borderRadius: 18, display: "grid", placeItems: "center", background: "linear-gradient(135deg, var(--mantine-color-brand-6), var(--mantine-color-dart-6))" }}>🎯</Box>
      )}
      <Text fw={800} fz={20} ta="center">{site.name}</Text>
    </Stack>
  );
}

/** Centered card for every page before login (no app menu). */
function LanguageSwitch() {
  const { site, urls } = usePage<SharedProps>().props;
  if (!urls.setLanguage) return null;
  const change = (language: string) => {
    // Django's set_language view (classic POST, then a full reload in the new language).
    const csrf = document.cookie.split("; ").find((c) => c.startsWith("csrftoken="))?.split("=")[1] ?? "";
    const f = document.createElement("form");
    f.method = "post";
    f.action = urls.setLanguage!;
    for (const [k, v] of Object.entries({ language, next: window.location.pathname.replace(/^\/en(?=\/)/, ""), csrfmiddlewaretoken: csrf })) {
      const i = document.createElement("input");
      i.type = "hidden";
      i.name = k;
      i.value = v;
      f.appendChild(i);
    }
    document.body.appendChild(f);
    f.submit();
  };
  return (
    <SegmentedControl size="xs" value={site.language === "en" ? "en" : "de"} onChange={change}
      data={[{ value: "de", label: "DE" }, { value: "en", label: "EN" }]} aria-label="Language" />
  );
}

function ThemeSwitch() {
  const t = useT();
  const { colorScheme, setColorScheme } = useMantineColorScheme();
  return (
    <SegmentedControl
      size="xs"
      value={colorScheme}
      onChange={(v) => {
        setColorScheme(v as MantineColorScheme);
        document.cookie = `dpm_theme=${v}; path=/; max-age=31536000; samesite=lax`;
      }}
      data={[
        { value: "auto", label: t("Auto") },
        { value: "light", label: t("Light") },
        { value: "dark", label: t("Dark") },
      ]}
      aria-label={t("Colour scheme")}
    />
  );
}

export function EntranceShell({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  useFlashToasts();
  const t = useT();
  const { urls, site } = usePage<SharedProps>().props;
  const fmt = useFormat();
  const b = site.build;
  return (
    <Box mih="100dvh" py={{ base: "md", sm: 40 }} px="md" style={{ background: "radial-gradient(1200px 500px at 50% -10%, var(--mantine-color-brand-light), transparent)" }}>
      <Box maw={wide ? 760 : 440} mx="auto">
        <Group justify="space-between" mb="lg">
          <LanguageSwitch />
          <ThemeSwitch />
        </Group>
        <Brand />
        {children}
        <Group justify="center" gap="md" mt="lg">
          {urls.imprint && <Anchor href={urls.imprint} size="xs" c="dimmed">{t("Imprint")}</Anchor>}
          {urls.privacy && <Anchor href={urls.privacy} size="xs" c="dimmed">{t("Privacy policy")}</Anchor>}
          {b && <Anchor href={b.github} target="_blank" rel="noopener" size="xs" c="dimmed">GitHub</Anchor>}
        </Group>
        {b && (
          <Text ta="center" size="xs" c="dimmed" mt={4}>
            <Anchor href={b.release} target="_blank" rel="noopener" size="xs" c="dimmed">v{b.version}</Anchor>
            {b.day && <> · {fmt.date(b.day)}</>}
            {" · "}
            {b.commitUrl ? <Anchor href={b.commitUrl} target="_blank" rel="noopener" size="xs" c="dimmed">{b.commit}</Anchor> : b.commit}
          </Text>
        )}
      </Box>
      <CookieNotice />
    </Box>
  );
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Paper withBorder shadow="md" radius="lg" p={{ base: "lg", sm: "xl" }}>
      <Title order={1} fz={24} mb="md">{title}</Title>
      {children}
    </Paper>
  );
}

function Message({ icon, children, links }: { icon?: ReactNode; children: ReactNode; links?: ReactNode }) {
  return (
    <Stack gap="md">
      <Group wrap="nowrap" align="flex-start" gap="sm">
        {icon}
        <Text size="sm">{children}</Text>
      </Group>
      {links}
    </Stack>
  );
}

function QrLogin({ qr }: { qr: NonNullable<Props["qr"]> }) {
  const t = useT();
  const [failed, setFailed] = useState<string | null>(null);
  useEffect(() => {
    const match = /(?:^#|&)t=([^&]+)/.exec(window.location.hash || "");
    if (!match) {
      setFailed(t("This QR code is no longer valid. Please log in manually."));
      return;
    }
    history.replaceState(null, "", window.location.pathname); // drop the token from the address bar
    const data = new FormData();
    data.append("token", decodeURIComponent(match[1]));
    data.append("legacy", qr.legacy ? "1" : "0");
    const csrf = document.cookie.split("; ").find((c) => c.startsWith("csrftoken="))?.split("=")[1] ?? "";
    fetch(qr.postUrl, { method: "POST", body: data, credentials: "same-origin", headers: { "X-CSRFToken": csrf } })
      .then((r) => r.json())
      .then((res) => {
        if (res.redirect) window.location.replace(res.redirect);
        else setFailed(res.detail || t("This QR code is no longer valid. Please log in manually."));
      })
      .catch(() => setFailed(t("This QR code is no longer valid. Please log in manually.")));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return failed ? (
    <Stack>
      <Alert color="yellow" icon={<IconAlertTriangle />}>{failed}</Alert>
      <Button component={Link} href="/accounts/login/" fullWidth>{t("Log in manually")}</Button>
    </Stack>
  ) : (
    <Center py="lg">
      <Stack align="center" gap="sm">
        <Loader />
        <Text>{t("Logging you in…")}</Text>
      </Stack>
    </Center>
  );
}

export default function Entrance(p: Props) {
  const t = useT();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const form = useForm<Record<string, any>>(initialData(p.fields) as Record<string, any>);
  const errors: Record<string, string> = { ...p.errors, ...(form.errors as Record<string, string>) };
  const submit = (label: string, extra?: ReactNode) => (
    <form onSubmit={(e) => { e.preventDefault(); form.post(p.action); }}>
      <Stack gap="md">
        {errors.form && <Alert color="red" icon={<IconAlertTriangle />}>{errors.form}</Alert>}
        <FormFields fields={p.fields} data={form.data} setData={(n, v) => form.setData((d: Record<string, unknown>) => ({ ...d, [n]: v }))} errors={errors} />
        <Button type="submit" size="md" fullWidth loading={form.processing}>{label}</Button>
        {extra}
      </Stack>
    </form>
  );
  const toLogin = <Button component={Link} href="/accounts/login/" color="gray" fullWidth>{t("Back to login")}</Button>;

  let title = "";
  let body: ReactNode = null;
  switch (p.kind) {
    case "login":
      title = t("Login");
      body = submit(t("Sign in"), (
        <>
          <Text size="xs" c="dimmed" ta="center">{t("Were you invited? Use the link in your invitation e-mail.")}</Text>
          <Group justify="space-between">
            <Anchor component={Link} href="/accounts/password/reset/" size="sm">{t("Forgot your password?")}</Anchor>
            <Anchor component={Link} href="/accounts/signup/" size="sm">{t("Create an account")}</Anchor>
          </Group>
        </>
      ));
      break;
    case "signup":
      title = t("Create an account");
      body = (
        <Stack gap="md">
          <Alert color="blue" variant="light">{t("After registration, an administrator must release your account before you can log in. You will receive an e-mail as soon as your account is active.")}</Alert>
          {submit(t("Register"), (
            <Text size="sm" ta="center">{t("Already have an account?")} <Anchor component={Link} href="/accounts/login/">{t("Sign in")}</Anchor></Text>
          ))}
        </Stack>
      );
      break;
    case "password_reset":
      title = t("Password reset");
      body = (
        <Stack gap="md">
          <Text size="sm" c="dimmed">{t("Forgotten your password? Enter your e-mail address below and we will send you a link to set a new one.")}</Text>
          {submit(t("Send reset link"), <Anchor component={Link} href="/accounts/login/" size="sm" ta="center">{t("Back to login")}</Anchor>)}
        </Stack>
      );
      break;
    case "password_reset_done":
      title = t("Password reset");
      body = <Message icon={<IconMailCheck color="var(--mantine-color-teal-filled)" />} links={toLogin}>{t("We have sent you an e-mail. If you have not received it, please check your spam folder.")}</Message>;
      break;
    case "password_reset_key":
      title = p.tokenFail ? t("Invalid link") : t("Set new password");
      body = p.tokenFail ? (
        <Message icon={<IconAlertTriangle color="var(--mantine-color-red-filled)" />} links={<Button component={Link} href="/accounts/password/reset/" fullWidth>{t("Request a new link.")}</Button>}>
          {t("The password reset link was invalid or has already been used.")}
        </Message>
      ) : submit(t("Set new password"));
      break;
    case "password_reset_key_done":
      title = t("Password changed");
      body = <Message icon={<IconCircleCheck color="var(--mantine-color-teal-filled)" />} links={toLogin}>{t("Your password is now changed.")}</Message>;
      break;
    case "verification_sent":
      title = t("Confirm your e-mail address");
      body = (
        <Message icon={<IconMailCheck color="var(--mantine-color-teal-filled)" />} links={toLogin}>
          {t("We have sent you an e-mail for verification. Follow the link in the message to finalize your registration. If you do not see the e-mail, check your spam folder.")}{" "}
          {t("Your account will be activated by an administrator after the registration has been checked.")}
        </Message>
      );
      break;
    case "email_confirm":
      title = t("Confirm e-mail address");
      body = !p.confirmation ? (
        <Message icon={<IconAlertTriangle color="var(--mantine-color-red-filled)" />} links={toLogin}>{t("This confirmation link expired or is invalid. Please request a new confirmation e-mail after logging in.")}</Message>
      ) : p.confirmation.canConfirm ? (
        <Stack>
          <Text size="sm">{t("Please confirm that %(email)s is your e-mail address.", { email: p.confirmation.email })}</Text>
          <Button size="md" fullWidth onClick={() => router.post(p.confirmation!.action)}>{t("Confirm")}</Button>
        </Stack>
      ) : (
        <Message icon={<IconAlertTriangle color="var(--mantine-color-red-filled)" />} links={toLogin}>{t("Unable to confirm this address because it is already confirmed by a different account.")}</Message>
      );
      break;
    case "logout":
      title = t("Logout");
      body = (
        <Stack>
          <Text size="sm">{t("Do you really want to log out?")}</Text>
          <Group grow>
            <Button color="gray" component={Link} href="/">{t("Cancel")}</Button>
            <Button color="red" onClick={() => router.post("/accounts/logout/")}>{t("Logout")}</Button>
          </Group>
        </Stack>
      );
      break;
    case "password_change":
      title = t("Change password");
      body = submit(t("Change password"), <Button component={Link} href="/accounts/settings/" color="gray" fullWidth>{t("Cancel")}</Button>);
      break;
    case "inactive":
      title = t("Account inactive");
      body = <Message icon={<IconAlertTriangle color="var(--mantine-color-red-filled)" />} links={toLogin}>{t("This account is inactive.")}</Message>;
      break;
    case "invite_accept": {
      const inv = p.invitation!;
      title = t("Accept your invitation");
      body = inv.error ? (
        <Message icon={<IconAlertTriangle color="var(--mantine-color-red-filled)" />} links={toLogin}>
          {inv.error} {t("Please contact the club if you think you should still have access.")}
        </Message>
      ) : (
        <Stack gap="md">
          <Paper withBorder p="sm" radius="md" bg="var(--mantine-color-default-hover)">
            <Text fw={700}>{inv.email}</Text>
            <Text size="sm" c="dimmed">
              {t("Role")}: {inv.role}{inv.team ? ` · ${t("Team")}: ${inv.team}` : ""}
            </Text>
            {inv.player && <Text size="sm">{t("You will play as %(player)s.", { player: inv.player })}</Text>}
          </Paper>
          {submit(t("Set password and activate account"))}
        </Stack>
      );
      break;
    }
    case "unsubscribe": {
      const u = p.unsubscribe!;
      title = t("Unsubscribe");
      const settingsLink = <Anchor href="/accounts/settings/" size="sm" ta="center">{t("E-mail settings")}</Anchor>;
      body = !u.valid ? (
        <Message icon={<IconAlertTriangle color="var(--mantine-color-red-filled)" />} links={settingsLink}>{t("This link is invalid. Change your e-mail settings after logging in.")}</Message>
      ) : u.done ? (
        <Message icon={<IconCircleCheck color="var(--mantine-color-teal-filled)" />} links={settingsLink}>
          {t('Done – you will no longer receive "%(label)s" e-mails.', { label: u.label })} {t("You can switch it on again at any time in your settings.")}
        </Message>
      ) : (
        <Stack>
          <Text size="sm">{t('Stop receiving "%(label)s" e-mails?', { label: u.label })}</Text>
          <Button size="md" fullWidth onClick={() => router.post(p.action)}>{t("Unsubscribe")}</Button>
          {settingsLink}
        </Stack>
      );
      break;
    }
    case "qr_login":
      title = t("QR login");
      body = <QrLogin qr={p.qr!} />;
      break;
  }

  return (
    <>
      <Head title={title} />
      <Card title={title}>{body}</Card>
    </>
  );
}

// Logged-in pages (password change) keep the app shell; all others get the entrance card.
Entrance.layout = (page: ReactNode & { props?: Props }) => {
  const kind = (page as { props?: Props }).props?.kind;
  return kind === "password_change" || kind === "logout" ? <AppLayout>{page}</AppLayout> : <EntranceShell>{page}</EntranceShell>;
};
