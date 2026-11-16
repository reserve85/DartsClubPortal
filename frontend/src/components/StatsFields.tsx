import { Grid, NumberInput, TagsInput, Text } from "@mantine/core";
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

/**
 * Optional dart statistics side by side. Inputs only accept plausible values:
 * 180s <= 3 per leg, high finishes 100-170 (no bogey numbers) and at most one
 * per won leg, low darts 9-21 per won leg, average 0-180.
 */
export function StatsFields({
  values,
  set,
  names,
  legsA,
  legsB,
  limits,
  errors,
}: {
  values: StatValues;
  set: (key: keyof StatValues, value: unknown) => void;
  names: [string, string];
  legsA: number;
  legsB: number;
  limits: Limits;
  errors: Record<string, string | undefined>;
}) {
  const t = useT();
  const legs = legsA + legsB;
  const hfOk = (v: string) => { const n = Number(v); return Number.isInteger(n) && n >= limits.hfMin && n <= limits.hfMax && !IMPOSSIBLE.has(n); };
  const ldOk = (v: string) => { const n = Number(v); return Number.isInteger(n) && n >= limits.ldMin && n <= limits.ldMax; };
  const col = (side: "a" | "b", won: number) => (
    <Grid.Col span={6}>
      <Text fw={800} size="sm" truncate mb={6}>{names[side === "a" ? 0 : 1]}</Text>
      <NumberInput
        label="180er"
        min={0}
        max={Math.max(0, legs * 3)}
        clampBehavior="strict"
        allowDecimal={false}
        value={values[`${side}_180s`]}
        onChange={(v) => set(`${side}_180s`, v)}
        error={errors[`${side}_180s`]}
        mb="xs"
      />
      <TagsInput
        label={t("High finishes")}
        placeholder={won ? `${limits.hfMin}–${limits.hfMax}` : "–"}
        disabled={!won}
        maxTags={won}
        splitChars={[",", " ", ";"]}
        value={values[`${side}_high_finishes`]}
        onChange={(v) => set(`${side}_high_finishes`, v.filter(hfOk))}
        error={errors[`${side}_high_finishes`]}
        mb="xs"
      />
      <TagsInput
        label={t("Low darts")}
        placeholder={won ? `${limits.ldMin}–${limits.ldMax}` : "–"}
        disabled={!won}
        maxTags={won}
        splitChars={[",", " ", ";"]}
        value={values[`${side}_low_darts`]}
        onChange={(v) => set(`${side}_low_darts`, v.filter(ldOk))}
        error={errors[`${side}_low_darts`]}
        mb="xs"
      />
      <NumberInput
        label={t("Average")}
        min={0}
        max={180}
        decimalScale={2}
        clampBehavior="strict"
        value={values[`${side}_average`]}
        onChange={(v) => set(`${side}_average`, v)}
        error={errors[`${side}_average`]}
      />
    </Grid.Col>
  );
  return (
    <Grid gap="md">
      {col("a", legsA)}
      {col("b", legsB)}
    </Grid>
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
