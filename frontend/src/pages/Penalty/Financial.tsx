import { Head, Link, router } from "@inertiajs/react";
import { Alert, Badge, Box, Button, Grid, Group, Modal, NumberInput, Paper, ScrollArea, Select, Table, Tabs, Text, Tooltip } from "@mantine/core";
import { IconCash, IconCrown, IconInfoCircle, IconReceiptRefund } from "@tabler/icons-react";
import { useState } from "react";
import { BalanceTiles } from "../../components/BalanceTiles";
import { confirmPost } from "../../components/elo";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { EmptyState, PageHeader } from "../../components/ui";
import { useFormat, useT } from "../../i18n";

interface Bal { playerId: number; name: string; avatar: string; total: number; paid: number; balance: number; isCaptain: boolean; isCashier: boolean }
interface PenaltyRow { id: number; date: string; player: string; matchday: string; matchdayId: number; description: string; amount: number }
interface Props {
  seasons: { id: number; name: string; isDefault: boolean }[];
  seasonId: number | null;
  teams: { id: number; name: string }[];
  teamId: number | null;
  own: null | { noPlayerLink?: boolean; name?: string; avatar?: string; total?: number; paid?: number; balance?: number; penalties?: PenaltyRow[] };
  team: null | {
    id: number; name: string; captains: string[]; cashier: string | null; canManage: boolean; isCashier: boolean;
    total: number; paid: number; balance: number; balances: Bal[]; inactive: Bal[];
    payments: { id: number; date: string; player: string; amount: number; receivedBy: string }[];
    matchdays: { id: number; label: string; date: string; total: number; isToday: boolean; isPast: boolean }[];
    mostCommon: { description: string; count: number; total: number }[];
    catalog: { description: string; amount: number; manual: boolean }[];
    penalties: PenaltyRow[];
  };
}

function PenaltyTable({ rows, showPlayer = true }: { rows: PenaltyRow[]; showPlayer?: boolean }) {
  const t = useT();
  const f = useFormat();
  if (!rows.length) return <EmptyState>{t("No penalties yet.")}</EmptyState>;
  return (
    <Paper withBorder style={{ overflow: "hidden" }}>
      {rows.map((p) => (
        <Group key={p.id} px="md" py={8} wrap="nowrap" style={{ borderBottom: "1px solid var(--mantine-color-default-border)" }}>
          <Box style={{ flex: 1, minWidth: 0 }}>
            <Text fw={700} truncate>{showPlayer ? p.player : p.description}</Text>
            <Text size="xs" c="dimmed" truncate>{showPlayer ? `${p.description} · ` : ""}{p.matchday}</Text>
          </Box>
          <Text fw={800} c="red" className="num" style={{ whiteSpace: "nowrap" }}>{f.euro(p.amount)}</Text>
        </Group>
      ))}
    </Paper>
  );
}

export default function Financial({ seasons, seasonId, teams, teamId, own, team }: Props) {
  const t = useT();
  const f = useFormat();
  const [pay, setPay] = useState<null | { row: Bal; payout: boolean }>(null);
  const [amount, setAmount] = useState<number | string>("");
  const here = window.location.pathname + window.location.search;
  const openPay = (row: Bal, payout: boolean) => { setPay({ row, payout }); setAmount(Math.abs(row.balance) || ""); };
  const submitPay = () => {
    if (!pay || !team) return;
    router.post(pay.payout ? "/payments/payout/" : "/payments/add/", { team: team.id, player: pay.row.playerId, amount_eur: amount, next: here }, { preserveScroll: true, onSuccess: () => setPay(null) });
  };

  const balanceRow = (b: Bal) => (
    <Group key={b.playerId} px="md" py={10} wrap="nowrap" gap="sm" style={{ borderBottom: "1px solid var(--mantine-color-default-border)" }}>
      <PlayerAvatar name={b.name} src={b.avatar} size={34} />
      <Box style={{ flex: 1, minWidth: 0 }}>
        <Group gap={4} wrap="nowrap">
          <Text fw={700} truncate component={Link} href={`/players/${b.playerId}/`} c="inherit" td="none">{b.name}</Text>
          {b.isCaptain && <Tooltip label={t("Captain")}><IconCrown size={15} color="var(--mantine-color-yellow-6)" /></Tooltip>}
          {b.isCashier && <Tooltip label={t("Cashier")}><IconCash size={15} color="var(--mantine-color-teal-6)" /></Tooltip>}
        </Group>
        <Text size="xs" c="dimmed" className="num">{t("Penalties total")} {f.euro(b.total)} · {t("Penalties settled")} {f.euro(b.paid)}</Text>
      </Box>
      <Box ta="right">
        <Text fw={800} className="num" c={b.balance > 0 ? "red" : b.balance < 0 ? "teal" : "dimmed"}>
          {b.balance < 0 ? `${t("Credit")} ${f.euro(-b.balance)}` : f.euro(b.balance)}
        </Text>
        {team?.isCashier && b.balance > 0 && <Button size="compact-xs" color="green" mt={4} leftSection={<IconCash size={12} />} onClick={() => openPay(b, false)}>{t("Record payment")}</Button>}
        {team?.isCashier && b.balance < 0 && <Button size="compact-xs" color="green" mt={4} leftSection={<IconReceiptRefund size={12} />} onClick={() => openPay(b, true)}>{t("Pay out")}</Button>}
      </Box>
    </Group>
  );

  return (
    <>
      <Head title={t("Financial overview")} />
      <PageHeader title={t("Financial overview")}>
        <Grid gap="sm">
          <Grid.Col span={6}>
            <Select label={t("Team")} data={teams.map((x) => ({ value: String(x.id), label: x.name }))} value={teamId ? String(teamId) : null}
              onChange={(v) => router.get("/financial/", { team: v }, { preserveScroll: true, preserveState: true })} />
          </Grid.Col>
          <Grid.Col span={6}>
            <Select label={t("Season")} data={seasons.map((s) => ({ value: String(s.id), label: s.isDefault ? `${s.name} (${t("default")})` : s.name }))} value={seasonId ? String(seasonId) : null}
              onChange={(v) => router.post("/seasons/set/", { season: v, next: here }, { preserveScroll: true })} />
          </Grid.Col>
        </Grid>
      </PageHeader>

      {own && (
        <Paper withBorder p="md" mb="md">
          <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb="sm">{t("My penalties")}</Text>
          {own.noPlayerLink ? (
            <Text c="dimmed" size="sm">{t("Your account is not linked to a player yet.")}</Text>
          ) : (
            <BalanceTiles total={own.total ?? 0} paid={own.paid ?? 0} balance={own.balance ?? 0} />
          )}
        </Paper>
      )}

      {!team ? (
        <EmptyState>{t("No team in this season yet.")}</EmptyState>
      ) : (
        <>
          <Paper withBorder p="md" className="hero">
            <Group justify="space-between" mb="sm" wrap="nowrap">
              <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
                <PlayerAvatar name={team.name} size={44} />
                <Box style={{ minWidth: 0 }}>
                  <Text fw={800} size="lg" truncate>{team.name}</Text>
                  <Text size="xs" c="dimmed" truncate>
                    {team.captains.length ? `${t("Captain")}: ${team.captains.join(", ")}` : t("No captain yet")}
                    {" · "}{t("Cashier")}: {team.cashier ?? "–"}
                  </Text>
                </Box>
              </Group>
              {!team.canManage && <Badge color="gray" variant="outline" style={{ flexShrink: 0 }}>{t("read only")}</Badge>}
            </Group>
            {!team.cashier && (
              <Alert color="yellow" icon={<IconInfoCircle />} mb="sm">
                {t("No cashier has been set for this team yet.")}{" "}
                {team.canManage && <Text component={Link} href="/teams/cashier/" inherit td="underline">{t("Set cashier")}</Text>}
              </Alert>
            )}
            <BalanceTiles total={team.total} paid={team.paid} balance={team.balance} />
          </Paper>

          <Tabs defaultValue="players" mt="md" keepMounted={false}>
            <ScrollArea type="never">
              <Tabs.List style={{ flexWrap: "nowrap" }}>
                <Tabs.Tab value="players">{t("Players")}</Tabs.Tab>
                <Tabs.Tab value="penalties">{t("Penalties")}</Tabs.Tab>
                <Tabs.Tab value="payments">{t("Payments")}</Tabs.Tab>
                <Tabs.Tab value="matchdays">{t("Matchdays")}</Tabs.Tab>
                <Tabs.Tab value="stats">{t("Most common")}</Tabs.Tab>
                <Tabs.Tab value="catalog">{t("Price list")}</Tabs.Tab>
              </Tabs.List>
            </ScrollArea>
            <Tabs.Panel value="players" pt="md">
              {team.balances.length ? <Paper withBorder style={{ overflow: "hidden" }}>{team.balances.map(balanceRow)}</Paper> : <EmptyState>{t("No players in this team yet.")}</EmptyState>}
              {team.inactive.length > 0 && (
                <>
                  <Text size="xs" fw={800} tt="uppercase" c="dimmed" mt="md" mb={6}>{t("Inactive players with open amounts")}</Text>
                  <Paper withBorder style={{ overflow: "hidden" }}>{team.inactive.map(balanceRow)}</Paper>
                </>
              )}
            </Tabs.Panel>
            <Tabs.Panel value="penalties" pt="md"><PenaltyTable rows={team.penalties} /></Tabs.Panel>
            <Tabs.Panel value="payments" pt="md">
              {team.payments.length ? (
                <Paper withBorder style={{ overflow: "hidden" }}>
                  {team.payments.map((p) => (
                    <Group key={p.id} px="md" py={8} wrap="nowrap" style={{ borderBottom: "1px solid var(--mantine-color-default-border)" }}>
                      <Box style={{ flex: 1, minWidth: 0 }}>
                        <Text fw={700} truncate>{p.player}</Text>
                        <Text size="xs" c="dimmed">{f.date(p.date)}{p.receivedBy ? ` · ${t("Cashier")}: ${p.receivedBy}` : ""}</Text>
                      </Box>
                      <Text fw={800} className="num" c={p.amount < 0 ? "orange" : "teal"}>{f.euro(p.amount)}</Text>
                      {team.isCashier && (
                        <Button size="compact-xs" color="red" onClick={() => confirmPost({ title: t("Revert payment?"), body: `${p.player} · ${f.euro(p.amount)}`, confirm: t("Revert"), cancel: t("Cancel"), url: `/payments/${p.id}/delete/` })}>
                          {t("Revert")}
                        </Button>
                      )}
                    </Group>
                  ))}
                </Paper>
              ) : <EmptyState>{t("No payments yet.")}</EmptyState>}
            </Tabs.Panel>
            <Tabs.Panel value="matchdays" pt="md">
              {team.matchdays.length ? (
                <Paper withBorder style={{ overflow: "hidden" }}>
                  {team.matchdays.map((m) => (
                    <Group key={m.id} px="md" py={10} wrap="nowrap" style={{ borderBottom: "1px solid var(--mantine-color-default-border)", opacity: m.isPast ? 0.7 : 1, background: m.isToday ? "var(--mantine-color-teal-light)" : undefined }}>
                      {m.isToday && <Badge color="teal" variant="filled">{t("Today")}</Badge>}
                      {team.canManage ? (
                        <Text fw={600} style={{ flex: 1 }} truncate component={Link} href={`/matchdays/${m.id}/`} c="inherit">{m.label}</Text>
                      ) : (
                        <Text fw={600} style={{ flex: 1 }} truncate>{m.label}</Text>
                      )}
                      <Text fw={800} className="num" c={m.total ? "red" : "dimmed"}>{f.euro(m.total)}</Text>
                    </Group>
                  ))}
                </Paper>
              ) : <EmptyState>{t("No matchdays yet.")}</EmptyState>}
            </Tabs.Panel>
            <Tabs.Panel value="stats" pt="md">
              {team.mostCommon.length ? (
                <Table striped withTableBorder>
                  <Table.Tbody>
                    {team.mostCommon.map((r) => (
                      <Table.Tr key={r.description}>
                        <Table.Td>{r.description}</Table.Td>
                        <Table.Td ta="right" className="num">{r.count}×</Table.Td>
                        <Table.Td ta="right" className="num" c="red">{f.euro(r.total)}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              ) : <EmptyState>{t("No penalties yet.")}</EmptyState>}
            </Tabs.Panel>
            <Tabs.Panel value="catalog" pt="md">
              <Table striped withTableBorder>
                <Table.Tbody>
                  {team.catalog.map((c) => (
                    <Table.Tr key={c.description}>
                      <Table.Td>{c.description}{c.manual ? " *" : ""}</Table.Td>
                      <Table.Td ta="right" className="num">{f.euro(c.amount)}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
              {team.catalog.some((c) => c.manual) && <Text size="xs" c="dimmed" mt="xs">* {t("Special penalty: the amount is entered individually; the fee shown is the default.")}</Text>}
            </Tabs.Panel>
          </Tabs>
        </>
      )}

      {own?.penalties && own.penalties.length > 0 && (
        <Box mt="lg">
          <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb={6}>{t("My penalties")}</Text>
          <PenaltyTable rows={own.penalties} showPlayer={false} />
        </Box>
      )}

      <Modal opened={!!pay} onClose={() => setPay(null)} title={<Text fw={800}>{pay?.payout ? t("Pay out credit") : t("Record payment")}</Text>}>
        {pay && (
          <>
            <Group mb="md"><PlayerAvatar name={pay.row.name} src={pay.row.avatar} size={40} /><Box><Text fw={700}>{pay.row.name}</Text><Text size="xs" c="dimmed">{pay.payout ? t("Credit") : t("Penalties open")}: {f.euro(Math.abs(pay.row.balance))}</Text></Box></Group>
            <NumberInput label={t("Amount (EUR)")} value={amount} onChange={setAmount} min={0.01} max={pay.payout ? Math.abs(pay.row.balance) : undefined} decimalScale={2} fixedDecimalScale step={1} suffix=" €" data-autofocus />
            <Group mt="lg" justify="flex-end">
              <Button color="gray" onClick={() => setPay(null)}>{t("Cancel")}</Button>
              <Button color="green" onClick={submitPay} disabled={!amount || Number(amount) <= 0}>{pay.payout ? t("Pay out") : t("Record payment")}</Button>
            </Group>
          </>
        )}
      </Modal>
    </>
  );
}
