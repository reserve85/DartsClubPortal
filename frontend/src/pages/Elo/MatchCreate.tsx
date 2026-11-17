import { useEffect, useState } from "react";
import { Head, Link, useForm } from "@inertiajs/react";
import { Accordion, Alert, Button, Grid, Group, Paper, Select, Stack, Text } from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { IconAlertTriangle, IconDeviceFloppy, IconPlayerTrackNext } from "@tabler/icons-react";
import dayjs from "dayjs";
import { type PickPlayer, PlayerSelect, ScoreChips } from "../../components/elo";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { type Limits, StatsFields, statsProblems, type StatValues } from "../../components/StatsFields";
import { PageHeader } from "../../components/ui";
import { useT } from "../../i18n";
import { joinLists } from "../../components/StatsFields";

interface Props {
  players: PickPlayer[];
  defaults: { playerA?: number | string | null; playerB?: number | string | null };
  bestOfChoices: number[];
  defaultBestOf: number;
  today: string;
  duplicate: boolean;
  errors: Record<string, string>;
  limits: Limits;
}

const num = (v: unknown) => (v === null || v === undefined || v === "" ? null : Number(v));

export default function MatchCreate({ players, defaults, bestOfChoices, defaultBestOf, today, duplicate, errors, limits }: Props) {
  const t = useT();
  const form = useForm({
    player_a: num(defaults.playerA),
    player_b: num(defaults.playerB),
    match_date: today,
    best_of_legs: defaultBestOf,
    score_a: null as number | null,
    score_b: null as number | null,
    a_180s: "" as number | string,
    b_180s: "" as number | string,
    a_high_finishes: [] as string[],
    b_high_finishes: [] as string[],
    a_low_darts: [] as string[],
    b_low_darts: [] as string[],
    a_average: "" as number | string,
    b_average: "" as number | string,
    force: false,
    again: false,
  });
  const d = form.data;
  const [statsOpen, setStatsOpen] = useState<string | null>(null);
  const pa = players.find((p) => p.id === d.player_a);
  const pb = players.find((p) => p.id === d.player_b);
  // A match can't be older than the later entry date of both players.
  const minDate = [pa?.entryDate, pb?.entryDate].filter(Boolean).sort().pop();
  const statsCtx = { names: [pa?.name ?? t("Player A"), pb?.name ?? t("Player B")] as [string, string], bestOf: d.best_of_legs, scoreA: d.score_a, scoreB: d.score_b };
  const statsBad = Object.keys(statsProblems(t, d as unknown as StatValues, statsCtx)).length > 0;
  const ready = d.player_a && d.player_b && d.score_a !== null && d.score_b !== null && d.match_date && !statsBad;
  useEffect(() => {
    if (statsBad) setStatsOpen("stats");
  }, [statsBad]);
  const submit = (again: boolean, force = false) => {
    form.transform((data) => ({ ...data, again, force, ...joinLists(data) }));
    form.post("/elo/matches/new/", { preserveScroll: "errors" });
  };

  const side = (key: "player_a" | "player_b", p: PickPlayer | undefined, other: number | null, color: string) => (
    <Grid.Col span={6}>
      <Stack align="center" gap={8}>
        {p ? <PlayerAvatar name={p.name} src={p.avatar} size={64} /> : <PlayerAvatar name={key === "player_a" ? "A" : "B"} size={64} color={color} />}
        <PlayerSelect
          w="100%"
          players={players}
          value={d[key]}
          exclude={other}
          onChange={(id) => form.setData(key, id)}
          placeholder={t("Choose player")}
          aria-label={key === "player_a" ? t("Player A") : t("Player B")}
          error={errors[key]}
        />
        <Text size="xs" c="dimmed" h={16}>{p ? `Elo ${p.elo}` : ""}</Text>
      </Stack>
    </Grid.Col>
  );

  return (
    <>
      <Head title={t("Enter match")} />
      <PageHeader title={t("Enter match")} />
      <Paper withBorder p="md" className="hero">
        {errors.form && (
          <Alert color="red" icon={<IconAlertTriangle />} mb="md">{errors.form}</Alert>
        )}
        {duplicate && (
          <Alert color="yellow" icon={<IconAlertTriangle />} mb="md" title={t("Possible duplicate")}>
            {t("a match with the same result on the same day already exists.")}
            <Group mt="sm">
              <Button color="yellow" onClick={() => submit(false, true)} loading={form.processing}>{t("Save anyway")}</Button>
              <Button color="gray" component={Link} href="/elo/matches/">{t("Show matches")}</Button>
            </Group>
          </Alert>
        )}
        <Grid gap="sm">
          {side("player_a", pa, d.player_b, "brand")}
          {side("player_b", pb, d.player_a, "dart")}
        </Grid>

        <Text ta="center" fw={700} size="sm" c="dimmed" mt="md" mb={8}>{t("Result")}</Text>
        <ScoreChips
          names={[pa?.name ?? t("Player A"), pb?.name ?? t("Player B")]}
          bestOf={d.best_of_legs}
          scoreA={d.score_a}
          scoreB={d.score_b}
          onChange={(a, b) => form.setData((prev) => ({ ...prev, score_a: a, score_b: b }))}
        />
        {(errors.score_a || errors.score_b) && <Text c="red" size="sm" ta="center" mt={6}>{errors.score_a || errors.score_b}</Text>}

        <Grid gap="sm" mt="lg">
          <Grid.Col span={6}>
            <DatePickerInput
              label={t("Date")}
              value={d.match_date}
              maxDate={today}
              minDate={minDate}
              onChange={(v) => form.setData("match_date", v ? dayjs(v).format("YYYY-MM-DD") : today)}
              error={errors.match_date}
            />
          </Grid.Col>
          <Grid.Col span={6}>
            <Select
              label={t("Format")}
              value={String(d.best_of_legs)}
              data={bestOfChoices.map((n) => ({ value: String(n), label: t("Best of %(n)s", { n }) }))}
              onChange={(v) => form.setData((prev) => ({ ...prev, best_of_legs: Number(v), score_a: null, score_b: null }))}
            />
          </Grid.Col>
        </Grid>
      </Paper>

      <Accordion variant="separated" radius="lg" mt="md" value={statsOpen} onChange={setStatsOpen}>
        <Accordion.Item value="stats">
          <Accordion.Control>{t("Statistics (optional)")}</Accordion.Control>
          <Accordion.Panel>
            <StatsFields
              values={d as unknown as StatValues}
              set={(k, v) => form.setData(k, v as never)}
              ctx={statsCtx}
              limits={limits}
              errors={errors}
            />
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>

      <Stack gap="xs" mt="lg">
        <Button size="lg" leftSection={<IconDeviceFloppy />} disabled={!ready} loading={form.processing} onClick={() => submit(false)}>
          {t("Save match")}
        </Button>
        <Button color="dart" leftSection={<IconPlayerTrackNext size={18} />} disabled={!ready} loading={form.processing} onClick={() => submit(true)}>
          {t("Save + next")}
        </Button>
        <Button color="gray" component={Link} href="/elo/">{t("Cancel")}</Button>
        {statsBad ? (
          <Text size="xs" c="red" ta="center">{t("The statistics do not fit the result - please correct them.")}</Text>
        ) : (
          !ready && <Text size="xs" c="dimmed" ta="center">{t("Choose both players and the result.")}</Text>
        )}
      </Stack>
    </>
  );
}
