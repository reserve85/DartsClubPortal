import { Alert, Grid, NumberInput, TagsInput, Text } from "@mantine/core";
import { IconInfoCircle } from "@tabler/icons-react";
import { useState } from "react";
import { useT } from "../i18n";

const IMPOSSIBLE = new Set([169, 168, 166, 165, 163, 162, 159]);

export interface Limits {
  hfMin: number;
  hfMax: number;
  ldMin: number;
  ldMax: number;
}
export interface StatValues {
  a_180s: number | string;
  b_180s: number | string;
  a_high_finishes: string[];
  b_high_finishes: string[];
  a_low_darts: string[];
  b_low_darts: string[];
  a_average: number | string;
  b_average: number | string;
}

/** What the result allows. Without a result yet the widest Best-of limits apply. */
export interface StatsContext {
  names: [string, string];
  bestOf: number;
  scoreA: number | null;
  scoreB: number | null;
}

type T = ReturnType<typeof useT>;

function bounds(ctx: StatsContext) {
  const decided = ctx.scoreA !== null && ctx.scoreB !== null;
  const need = Math.ceil(ctx.bestOf / 2);
  return {
    decided,
    legs: decided ? (ctx.scoreA ?? 0) + (ctx.scoreB ?? 0) : ctx.bestOf,
    won: { a: decided ? (ctx.scoreA ?? 0) : need, b: decided ? (ctx.scoreB ?? 0) : need },
  };
}

/** Statistics that do not fit the result (or Best of): field -> message. Empty = fine. */
export function statsProblems(t: T, values: StatValues, ctx: StatsContext): Record<string, string> {
  const { decided, legs, won } = bounds(ctx);
  const out: Record<string, string> = {};
  (["a", "b"] as const).forEach((side, i) => {
    const name = ctx.names[i];
    const n180 = Number(values[`${side}_180s`] || 0);
    if (n180 > legs * 3) out[`${side}_180s`] = t("At most %(n)s 180s in %(legs)s legs.", { n: legs * 3, legs });
    const avg = values[`${side}_average`];
    if (avg !== "" && avg !== null && (Number(avg) < 0 || Number(avg) > 180)) out[`${side}_average`] = t("An average is between 0 and 180.");
    const lists = [
      ["high_finishes", t("high finishes")],
      ["low_darts", t("low darts entries")],
    ] as const;
    for (const [key, what] of lists) {
      const count = values[`${side}_${key}`].length;
      if (count > won[side]) {
        out[`${side}_${key}`] = !decided
          ? t("Best of %(n)s: at most %(won)s %(what)s per player.", { n: ctx.bestOf, won: won[side], what })
          : won[side] === 0
            ? t("%(name)s won no leg: remove the %(what)s.", { name, what })
            : t("Legs won by %(name)s: %(won)s - at most %(won)s %(what)s.", { name, won: won[side], what });
      }
    }
  });
  return out;
}

/**
 * Optional dart statistics side by side. They can be filled in before the
 * result: until then the limits of the chosen Best of apply, afterwards those
 * of the result. Values that do not fit are explained, never dropped silently.
 */
export function StatsFields({
  values,
  set,
  ctx,
  limits,
  errors,
}: {
  values: StatValues;
  set: (key: keyof StatValues, value: unknown) => void;
  ctx: StatsContext;
  limits: Limits;
  errors: Record<string, string | undefined>;
}) {
  const t = useT();
  const { decided, legs, won } = bounds(ctx);
  const problems = statsProblems(t, values, ctx);
  // Typed values that are no possible finish / low darts: say why they vanished.
  const [rejected, setRejected] = useState<Record<string, string>>({});
  const hfOk = (v: string) => { const n = Number(v); return Number.isInteger(n) && n >= limits.hfMin && n <= limits.hfMax && !IMPOSSIBLE.has(n); };
  const ldOk = (v: string) => { const n = Number(v); return Number.isInteger(n) && n >= limits.ldMin && n <= limits.ldMax; };
  const tags = (key: keyof StatValues, ok: (v: string) => boolean, why: (v: string) => string) => (list: string[]) => {
    const bad = list.filter((v) => !ok(v));
    setRejected((r) => ({ ...r, [key]: bad.length ? why(bad[bad.length - 1]) : "" }));
    set(key, list.filter(ok));
  };
  const message = (key: string) => errors[key] || problems[key] || rejected[key] || undefined;

  const col = (side: "a" | "b") => (
    <Grid.Col span={6}>
      <Text fw={800} size="sm" truncate mb={6}>{ctx.names[side === "a" ? 0 : 1]}</Text>
      <NumberInput
        label="180er"
        min={0}
        max={legs * 3}
        clampBehavior="none"
        allowDecimal={false}
        allowNegative={false}
        value={values[`${side}_180s`]}
        onChange={(v) => set(`${side}_180s`, v)}
        error={message(`${side}_180s`)}
        mb="xs"
      />
      <TagsInput
        label={t("High finishes")}
        placeholder={`${limits.hfMin}–${limits.hfMax}`}
        // Locked only when nothing is entered and the player won no leg.
        disabled={decided && won[side] === 0 && values[`${side}_high_finishes`].length === 0}
        splitChars={[",", " ", ";"]}
        value={values[`${side}_high_finishes`]}
        onChange={tags(`${side}_high_finishes`, hfOk, (v) =>
          t("%(v)s is no possible high finish (%(min)s–%(max)s, no bogey numbers).", { v, min: limits.hfMin, max: limits.hfMax }),
        )}
        error={message(`${side}_high_finishes`)}
        mb="xs"
      />
      <TagsInput
        label={t("Low darts")}
        placeholder={`${limits.ldMin}–${limits.ldMax}`}
        disabled={decided && won[side] === 0 && values[`${side}_low_darts`].length === 0}
        splitChars={[",", " ", ";"]}
        value={values[`${side}_low_darts`]}
        onChange={tags(`${side}_low_darts`, ldOk, (v) =>
          t("%(v)s is not possible: a leg takes %(min)s to %(max)s darts here.", { v, min: limits.ldMin, max: limits.ldMax }),
        )}
        error={message(`${side}_low_darts`)}
        mb="xs"
      />
      <NumberInput
        label={t("Average")}
        min={0}
        max={180}
        decimalScale={2}
        clampBehavior="none"
        allowNegative={false}
        value={values[`${side}_average`]}
        onChange={(v) => set(`${side}_average`, v)}
        error={message(`${side}_average`)}
      />
    </Grid.Col>
  );
  return (
    <>
      {!decided && (
        <Alert color="blue" variant="light" icon={<IconInfoCircle size={18} />} mb="sm">
          <Text size="sm">{t("No result yet: the limits of Best of %(n)s apply. The result checks the statistics again.", { n: ctx.bestOf })}</Text>
        </Alert>
      )}
      <Grid gap="md">
        {col("a")}
        {col("b")}
      </Grid>
    </>
  );
}

/** Statistics lists go to Django as "121, 100" (one text field per list). */
export function joinLists(d: Record<string, unknown>) {
  const out: Record<string, string> = {};
  for (const k of ["a_high_finishes", "b_high_finishes", "a_low_darts", "b_low_darts"]) {
    out[k] = ((d[k] as string[]) ?? []).join(", ");
  }
  return out;
}
