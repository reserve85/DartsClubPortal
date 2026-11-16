import { Head } from "@inertiajs/react";
import { Anchor, List, Paper, Stack, Text, Title } from "@mantine/core";
import type { ReactNode } from "react";
import AppLayout from "../layout/AppLayout";
import { EntranceShell } from "./Auth/Entrance";
import { PageHeader } from "../components/ui";
import { useT } from "../i18n";

interface Contact {
  company: string;
  name: string;
  street: string;
  city: string;
  email: string;
  imprintName: string;
  imprintUrl: string;
}
interface Props {
  kind: "imprint" | "privacy";
  contact: Contact;
}

function Address({ c, withEmail = true }: { c: Contact; withEmail?: boolean }) {
  const t = useT();
  return (
    <Text size="sm">
      {[c.company || c.imprintName, c.name, c.street, c.city].filter(Boolean).map((line) => (
        <span key={line}>{line}<br /></span>
      ))}
      {withEmail && c.email && <>{t("E-mail")}: <Anchor href={`mailto:${c.email}`}>{c.email}</Anchor></>}
    </Text>
  );
}

function H({ children }: { children: ReactNode }) {
  return <Title order={2} fz="lg" mt="md">{children}</Title>;
}

export default function Legal({ kind, contact: c }: Props) {
  const t = useT();
  const title = kind === "imprint" ? t("Imprint") : t("Privacy Policy");
  return (
    <>
      <Head title={title} />
      <PageHeader title={title} />
      <Paper withBorder p={{ base: "md", sm: "xl" }} radius="md">
        {kind === "imprint" ? (
          <Stack gap="xs">
            {c.company || c.name || c.imprintName || c.imprintUrl ? (
              <>
                <Address c={c} />
                {c.imprintName && c.company && c.imprintName !== c.company && <Text size="sm">{c.imprintName}</Text>}
                {c.imprintUrl && <Anchor href={c.imprintUrl} target="_blank" rel="noopener" size="sm">{c.imprintUrl}</Anchor>}
              </>
            ) : (
              <Text c="dimmed">{t("No imprint configured.")}</Text>
            )}
          </Stack>
        ) : (
          <Stack gap={6}>
            <H>{t("1. Responsible Party")}</H>
            <Address c={c} />
            <H>{t("2. Data We Collect")}</H>
            <Text size="sm">{t("This application stores the following data to provide its services:")}</Text>
            <List size="sm" spacing={4}>
              <List.Item>{t("User accounts: e-mail address, password hash, first and last name entered during registration (used to assign the player), role, team assignment and language/theme preferences.")}</List.Item>
              <List.Item>{t("Player and team data: names, team memberships and active status.")}</List.Item>
              <List.Item>{t("Elo data: matches, results, Elo values and dart statistics; an optional player picture.")}</List.Item>
              <List.Item>{t("Matchday and penalty data: dates, participants, penalties, payments and balances.")}</List.Item>
              <List.Item>{t("Audit logs: who changed which record and when.")}</List.Item>
              <List.Item>{t("Authentication cookies: a secure HttpOnly session cookie is used to keep you logged in.")}</List.Item>
            </List>
            <H>{t("3. Purpose of Data Processing")}</H>
            <Text size="sm">{t("Data is processed exclusively to run the club's Elo ranking and penalty system: matches and statistics, matchdays, balances and financial reporting, plus the e-mails you subscribed to.")}</Text>
            <H>{t("4. Cookies")}</H>
            <Text size="sm">{t("This website uses the following cookies:")}</Text>
            <List size="sm" spacing={4}>
              <List.Item>{t("Session cookie (HttpOnly):")} {t("Required for login sessions. This cookie is essential and cannot be declined.")}</List.Item>
              <List.Item>{t("CSRF and language cookies:")} {t("Required for secure forms and your language choice. These cookies are essential and cannot be declined.")}</List.Item>
              <List.Item>{t("Colour scheme cookie:")} {t("Remembers light or dark mode before login. Essential for the display.")}</List.Item>
              <List.Item>{t("Cookie consent flag:")} {t("Stored in your browser's localStorage after you confirm the cookie notice. This cookie is essential and cannot be declined.")}</List.Item>
            </List>
            <Text size="sm">{t("No third-party tracking or analytics cookies are used.")}</Text>
            <H>{t("5. Data Retention")}</H>
            <Text size="sm">{t("Data is retained as long as necessary for the operation of the penalty system. Matchday, penalty and audit records are preserved to maintain a complete financial history.")}</Text>
            <H>{t("6. Your Rights")}</H>
            <Text size="sm">{t("Under the GDPR, you have the right to:")}</Text>
            <List size="sm" spacing={4}>
              <List.Item>{t("Access your personal data")}</List.Item>
              <List.Item>{t("Rectify inaccurate data")}</List.Item>
              <List.Item>{t("Request deletion of your data")}</List.Item>
              <List.Item>{t("Object to data processing")}</List.Item>
              <List.Item>{t("Data portability")}</List.Item>
            </List>
            {c.email && <Text size="sm">{t("To exercise these rights, please contact us at")} <Anchor href={`mailto:${c.email}`}>{c.email}</Anchor>.</Text>}
            <H>{t("7. Data Security")}</H>
            <Text size="sm">{t("We implement appropriate technical and organizational measures to protect your data, including password hashing, CSRF protection, optional HTTPS enforcement and a full audit trail.")}</Text>
            <H>{t("8. Contact")}</H>
            <Text size="sm">{t("For questions about this privacy policy, please contact:")}</Text>
            <Address c={c} />
          </Stack>
        )}
      </Paper>
    </>
  );
}

// Signed in: inside the app; visitors: the entrance card layout.
Legal.layout = (page: ReactNode) => {
  const signedIn = Boolean((page as { props?: { auth?: { user?: unknown } } }).props?.auth?.user);
  return signedIn ? <AppLayout>{page}</AppLayout> : <EntranceShell wide>{page}</EntranceShell>;
};
