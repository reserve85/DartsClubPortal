import { Head, Link, useForm } from "@inertiajs/react";
import { Alert, Button, Grid, Group, Paper, Select, Text } from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { IconAlertTriangle } from "@tabler/icons-react";
import dayjs from "dayjs";
import { ScoreChips } from "../../components/elo";
import { type Limits, StatsFields, type StatValues } from "../../components/StatsFields";
import { PageHeader } from "../../components/ui";
import { useT } from "../../i18n";

interface Props {
  match: {
    id: number;
    a: string;
    b: string;
    date: string;
    bestOf: number;
    scoreA: number;
    scoreB: number;
    stats: Record<string, number | number[] | null>;
  };
  bestOfChoices: number[];
  today: string;
  duplicate: boolean;
  errors: Record<string, string>;
  limits: Limits;
}

const list = (v: unknown) => ((v as number[] | null) ?? []).map(String);
const val = (v: unknown) => (v === null || v === undefined ? "" : (v as number));

export default function MatchEdit({ match, bestOfChoices, today, duplicate, errors, limits }: Props) {
  const t = useT();
  const s = match.stats;
  const form = useForm({
    match_date: match.date,
    best_of_legs: match.bestOf,
    score_a: match.scoreA as number | null,
    score_b: match.scoreB as number | null,
    a_180s: val(s.a_180s),
    b_180s: val(s.b_180s),
    a_high_finishes: list(s.a_high_finishes),
    b_high_finishes: list(s.b_high_finishes),
    a_low_darts: list(s.a_low_darts),
    b_low_darts: list(s.b_low_darts),
    a_average: val(s.a_average),
    b_average: val(s.b_average),
    force: false,
  });
  const d = form.data;
  const save = (force = false) => {
    form.transform((data) => ({ ...data, force }));
    form.post(`/elo/matches/${match.id}/edit/`, { preserveScroll: true });
  };
  return (
    <>
      <Head title={t("Edit match")} />
      <PageHeader title={t("Edit match")} subtitle={`${match.a} – ${match.b}`} />
      {errors.form && <Alert color="red" icon={<IconAlertTriangle />} mb="md">{errors.form}</Alert>}
      {duplicate && (
        <Alert color="yellow" icon={<IconAlertTriangle />} mb="md">
          {t("A match with the same result on the same day already exists.")}
          <Group mt="sm"><Button color="yellow" onClick={() => save(true)}>{t("Save anyway")}</Button></Group>
        </Alert>
      )}
      <Paper withBorder p="md" className="hero">
        <Grid gap="sm" mb="md">
          <Grid.Col span={6}>
            <DatePickerInput label={t("Date")} value={d.match_date} maxDate={today} onChange={(v) => form.setData("match_date", v ? dayjs(v).format("YYYY-MM-DD") : d.match_date)} error={errors.match_date} />
          </Grid.Col>
          <Grid.Col span={6}>
            <Select
              label={t("Format")}
              value={String(d.best_of_legs)}
              data={bestOfChoices.map((n) => ({ value: String(n), label: t("Best of %(n)s", { n }) }))}
              onChange={(v) => form.setData((p) => ({ ...p, best_of_legs: Number(v), score_a: null, score_b: null }))}
            />
          </Grid.Col>
        </Grid>
        <Group justify="space-between" mb={6}><Text fw={700} size="sm">{match.a}</Text><Text fw={700} size="sm">{match.b}</Text></Group>
        <ScoreChips names={[match.a, match.b]} bestOf={d.best_of_legs} scoreA={d.score_a} scoreB={d.score_b} onChange={(a, b) => form.setData((p) => ({ ...p, score_a: a, score_b: b }))} />
      </Paper>
      <Paper withBorder p="md" mt="md">
        <StatsFields
          values={d as unknown as StatValues}
          set={(k, v) => form.setData(k, v as never)}
          names={[match.a, match.b]}
          legsA={d.score_a ?? 0}
          legsB={d.score_b ?? 0}
          limits={limits}
          errors={errors}
        />
      </Paper>
      <Text size="xs" c="dimmed" mt="sm">{t("Saving recalculates the Elo of every later match of both players.")}</Text>
      <Group mt="md">
        <Button onClick={() => save()} loading={form.processing} disabled={d.score_a === null}>{t("Save changes")}</Button>
        <Button color="gray" component={Link} href={`/elo/matches/${match.id}/`}>{t("Cancel")}</Button>
      </Group>
    </>
  );
}
