import { Head, Link } from "@inertiajs/react";
import { Box, Button, Grid, Group, Paper, Table, Text } from "@mantine/core";
import { IconEdit, IconSwords, IconTrash } from "@tabler/icons-react";
import { confirmPost } from "../../components/elo";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { Delta, PageHeader } from "../../components/ui";
import { useFormat, useT } from "../../i18n";

interface Side {
  id: number;
  name: string;
  avatar: string;
  score: number;
  won: boolean;
  eloBefore: number;
  eloAfter: number;
  eloChange: number;
  n180: number;
  hf: number[];
  ld: number[];
  average: number | null;
}
interface Props {
  match: { id: number; date: string; bestOf: number; kFactor: number; createdAt: string; createdBy: string };
  a: Side;
  b: Side;
  canEdit: boolean;
}

function SideBlock({ s }: { s: Side }) {
  const f = useFormat();
  return (
    <Box component={Link} href={`/elo/players/${s.id}/`} style={{ textDecoration: "none", color: "inherit", display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <PlayerAvatar name={s.name} src={s.avatar} size={72} style={s.won ? { boxShadow: "0 0 0 3px var(--mantine-color-body), 0 0 0 5px var(--mantine-color-teal-6)" } : undefined} />
      <Text fw={800} ta="center" lineClamp={2}>{s.name}</Text>
      <Text size="xs" c="dimmed" className="num">{f.elo(s.eloBefore)} → {f.elo(s.eloAfter)}</Text>
      <Delta value={s.eloChange} />
    </Box>
  );
}

export default function MatchDetail({ match, a, b, canEdit }: Props) {
  const t = useT();
  const f = useFormat();
  const row = (label: string, va: React.ReactNode, vb: React.ReactNode) => (
    <Table.Tr>
      <Table.Td ta="center" fw={700} className="num">{va}</Table.Td>
      <Table.Td ta="center"><Text size="xs" c="dimmed">{label}</Text></Table.Td>
      <Table.Td ta="center" fw={700} className="num">{vb}</Table.Td>
    </Table.Tr>
  );
  return (
    <>
      <Head title={`${a.name} – ${b.name}`} />
      <PageHeader title={t("Match")} subtitle={`${f.date(match.date)} · ${t("Best of %(n)s", { n: match.bestOf })}`} />
      <Paper withBorder p="lg" className="hero">
        <Grid align="center" gap="xs">
          <Grid.Col span={4.5}><SideBlock s={a} /></Grid.Col>
          <Grid.Col span={3}>
            <Text ta="center" fw={900} fz={44} className="num" lh={1}>
              <Text span inherit c={a.won ? "teal" : undefined}>{a.score}</Text>
              <Text span inherit c="dimmed">:</Text>
              <Text span inherit c={b.won ? "teal" : undefined}>{b.score}</Text>
            </Text>
          </Grid.Col>
          <Grid.Col span={4.5}><SideBlock s={b} /></Grid.Col>
        </Grid>
      </Paper>

      <Paper withBorder p="md" mt="md">
        <Text size="xs" fw={800} tt="uppercase" c="dimmed" mb="xs">{t("Statistics")}</Text>
        <Table verticalSpacing={6} withRowBorders>
          <Table.Tbody>
            {row("180er", a.n180 || "–", b.n180 || "–")}
            {row(t("High finishes"), a.hf.join(", ") || "–", b.hf.join(", ") || "–")}
            {row(t("Low darts"), a.ld.join(", ") || "–", b.ld.join(", ") || "–")}
            {row(t("Average"), a.average !== null ? f.number(a.average, 2) : "–", b.average !== null ? f.number(b.average, 2) : "–")}
          </Table.Tbody>
        </Table>
        <Text size="xs" c="dimmed" mt="sm">
          {t("K-factor")} {match.kFactor} · {match.createdBy ? `${t("entered by %(who)s", { who: match.createdBy })} · ` : ""}{match.createdAt}
        </Text>
      </Paper>

      <Group mt="md" gap="xs">
        <Button component={Link} href={`/elo/head-to-head/?a=${a.id}&b=${b.id}`} leftSection={<IconSwords size={16} />}>{t("Head-to-head")}</Button>
        {canEdit && (
          <>
            <Button color="yellow" component={Link} href={`/elo/matches/${match.id}/edit/`} leftSection={<IconEdit size={16} />}>{t("Edit")}</Button>
            <Button
              color="red"
              leftSection={<IconTrash size={16} />}
              onClick={() =>
                confirmPost({
                  title: t("Delete match?"),
                  body: t("The match is removed and the Elo of every later match of both players is recalculated. Both players are notified."),
                  confirm: t("Delete"),
                  cancel: t("Cancel"),
                  url: `/elo/matches/${match.id}/delete/`,
                })
              }
            >
              {t("Delete")}
            </Button>
          </>
        )}
      </Group>
      <Box h={8} />
    </>
  );
}
