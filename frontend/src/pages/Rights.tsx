import { Head } from "@inertiajs/react";
import { Badge, Box, Group, List, Paper, ScrollArea, SimpleGrid, Table, Text, ThemeIcon, Tooltip } from "@mantine/core";
import { IconCash, IconCheck, IconCrown, IconEye, IconMinus, IconShieldCheck, IconUser, IconUsers } from "@tabler/icons-react";
import { Fragment, type ReactNode } from "react";
import { PageHeader, Section } from "../components/ui";
import { useT } from "../i18n";

/** y = yes, o = own team only, r = read only, c = only the team's cashier, n = no */
type Cell = "y" | "o" | "r" | "c" | "n";
type Col = "admin" | "captain" | "cashier" | "user";

interface Props {
  me: {
    role: "system" | "admin" | "user" | "";
    isAdmin: boolean;
    captainOf: string | null;
    cashierOf: string[];
    hasPlayer: boolean;
    modules: { elo: boolean; penalty: boolean };
  };
}

export default function Rights({ me }: Props) {
  const t = useT();
  const cols: { key: Col; label: string; icon: ReactNode; color: string }[] = [
    { key: "admin", label: t("Admin"), icon: <IconShieldCheck size={16} />, color: "brand" },
    { key: "captain", label: t("Captain"), icon: <IconCrown size={16} />, color: "yellow" },
    { key: "cashier", label: t("Cashier"), icon: <IconCash size={16} />, color: "teal" },
    { key: "user", label: t("User"), icon: <IconUser size={16} />, color: "gray" },
  ];
  const groups: { title: string; rows: [string, Cell, Cell, Cell, Cell][] }[] = [
    {
      title: "Elo",
      rows: [
        [t("See the ranking, statistics, head-to-head and matches"), "y", "y", "y", "y"],
        [t("Enter a match"), "y", "y", "y", "y"],
        [t("Edit or delete matches"), "y", "n", "n", "n"],
        [t("Manage Elo players, recalculate, CSV exports"), "y", "n", "n", "n"],
      ],
    },
    {
      title: "Penalty",
      rows: [
        [t("See the own balance and the financial overview"), "y", "y", "y", "y"],
        [t("Matchdays: create, edit, add players"), "y", "o", "r", "n"],
        [t("Assign and edit penalties"), "y", "o", "n", "n"],
        [t("Players and team assignment"), "y", "o", "n", "n"],
        [t("Catalog: fee and active state per team"), "y", "o", "n", "n"],
        [t("Catalog: new entries, default fee, delete"), "y", "n", "n", "n"],
        [t("Cash box: choose the cashier"), "y", "o", "n", "n"],
        [t("Record payments and payouts"), "c", "c", "o", "n"],
      ],
    },
    {
      title: t("Administration"),
      rows: [
        [t("Users, invitations, approvals"), "y", "n", "n", "n"],
        [t("Seasons, teams, club logo"), "y", "n", "n", "n"],
        [t("Audit log, import, QR codes"), "y", "n", "n", "n"],
      ],
    },
  ];
  const mine: Record<Col, boolean> = {
    admin: me.isAdmin,
    captain: !!me.captainOf,
    cashier: me.cashierOf.length > 0,
    user: true,
  };
  const legend: Record<Cell, { icon: ReactNode; color: string; label: string }> = {
    y: { icon: <IconCheck size={14} />, color: "teal", label: t("allowed") },
    o: { icon: <IconUsers size={14} />, color: "yellow", label: t("own team only") },
    r: { icon: <IconEye size={14} />, color: "blue", label: t("read only") },
    c: { icon: <IconCash size={14} />, color: "teal", label: t("only as the team's cashier") },
    n: { icon: <IconMinus size={14} />, color: "gray", label: t("not allowed") },
  };
  const cell = (c: Cell) => (
    <Tooltip label={legend[c].label}>
      <ThemeIcon size={24} radius="xl" variant={c === "n" ? "subtle" : "light"} color={legend[c].color} aria-label={legend[c].label}>
        {legend[c].icon}
      </ThemeIcon>
    </Tooltip>
  );
  const roleLabel = { system: t("System"), admin: t("Admin"), user: t("User"), "": t("no role") }[me.role];

  return (
    <>
      <Head title={t("Who may do what?")} />
      <PageHeader
        title={t("Who may do what?")}
        subtitle={t("Roles: System, Admin, User. Captain and cashier are assignments on top.")}
        left={<IconShieldCheck size={40} stroke={1.5} />}
      />

      <Section title={t("Your account")}>
        <Paper withBorder p="md" radius="md">
          <Group gap={8} mb="sm">
            <Badge size="lg" color={me.isAdmin ? "brand" : "gray"} variant="filled">{roleLabel}</Badge>
            {me.captainOf && <Badge size="lg" color="yellow" variant="light" leftSection={<IconCrown size={14} />}>{t("Captain")}: {me.captainOf}</Badge>}
            {me.cashierOf.map((team) => (
              <Badge key={team} size="lg" color="teal" variant="light" leftSection={<IconCash size={14} />}>{t("Cashier")}: {team}</Badge>
            ))}
            <Badge size="lg" variant="outline" color={me.modules.elo ? "brand" : "gray"}>Elo {me.modules.elo ? "✓" : "–"}</Badge>
            <Badge size="lg" variant="outline" color={me.modules.penalty ? "brand" : "gray"}>Penalty {me.modules.penalty ? "✓" : "–"}</Badge>
          </Group>
          <List size="sm" spacing={4} icon={<ThemeIcon size={18} radius="xl" color="teal"><IconCheck size={12} /></ThemeIcon>}>
            {me.modules.elo && <List.Item>{me.isAdmin ? t("You run the Elo ranking: matches, players, corrections.") : t("You see the Elo ranking and enter your matches.")}</List.Item>}
            {me.modules.penalty && <List.Item>{t("You see your balance and the financial overview of every team.")}</List.Item>}
            {me.isAdmin && <List.Item>{t("You manage users, seasons, teams and every team's penalties.")}</List.Item>}
            {!me.isAdmin && me.captainOf && <List.Item>{t("As captain you manage matchdays, penalties, players and fees of %(team)s.", { team: me.captainOf })}</List.Item>}
            {me.cashierOf.length > 0 && <List.Item>{t("As cashier you record payments and payouts of %(teams)s.", { teams: me.cashierOf.join(", ") })}</List.Item>}
            {!me.isAdmin && !me.captainOf && me.modules.penalty && <List.Item>{t("Everything else of the penalty module is read only for you.")}</List.Item>}
          </List>
        </Paper>
      </Section>

      <Section title={t("Overview of all roles")}>
        <Paper withBorder radius="md">
          <ScrollArea type="auto">
            <Table verticalSpacing={8} miw={560} highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th style={{ position: "sticky", left: 0, background: "var(--mantine-color-body)", zIndex: 1 }} />
                  {cols.map((c) => (
                    <Table.Th key={c.key} ta="center" bg={mine[c.key] ? "var(--mantine-color-brand-light)" : undefined}>
                      <Group gap={4} justify="center" wrap="nowrap">
                        {c.icon}
                        <Text size="sm" fw={700}>{c.label}</Text>
                      </Group>
                      {mine[c.key] && <Text size="xs" c="dimmed">{t("you")}</Text>}
                    </Table.Th>
                  ))}
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {groups.map((g) => (
                  <Fragment key={g.title}>
                    <Table.Tr>
                      <Table.Td colSpan={5} bg="var(--mantine-color-default-hover)">
                        <Text size="xs" fw={800} tt="uppercase" c="dimmed">{g.title}</Text>
                      </Table.Td>
                    </Table.Tr>
                    {g.rows.map(([label, ...cells]) => (
                      <Table.Tr key={label}>
                        <Table.Td style={{ position: "sticky", left: 0, background: "var(--mantine-color-body)", zIndex: 1 }}>
                          <Text size="sm">{label}</Text>
                        </Table.Td>
                        {cells.map((c, i) => (
                          <Table.Td key={i} ta="center" bg={mine[cols[i].key] ? "var(--mantine-color-brand-light)" : undefined}>
                            <Box display="inline-block">{cell(c as Cell)}</Box>
                          </Table.Td>
                        ))}
                      </Table.Tr>
                    ))}
                  </Fragment>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        </Paper>
        <SimpleGrid cols={{ base: 1, xs: 2, md: 5 }} spacing="xs" mt="sm">
          {(Object.keys(legend) as Cell[]).map((k) => (
            <Group key={k} gap={6} wrap="nowrap">
              {cell(k)}
              <Text size="xs" c="dimmed">{legend[k].label}</Text>
            </Group>
          ))}
        </SimpleGrid>
        <Text size="xs" c="dimmed" mt="sm">
          {t("Captain and cashier are assignments: an admin can be captain of a team, a user can be cashier. A captain who is not an admin only changes the team they lead.")}
        </Text>
      </Section>
    </>
  );
}
