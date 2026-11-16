import { Chip, Group, NumberInput, SegmentedControl, Select, Stack, Text, type SelectProps } from "@mantine/core";
import { modals } from "@mantine/modals";
import { router } from "@inertiajs/react";
import type { ReactNode } from "react";
import { PlayerAvatar } from "./PlayerAvatar";

export interface PickPlayer {
  id: number;
  name: string;
  elo?: number;
  avatar?: string;
  disabled?: boolean;
  entryDate?: string;
}

/** Searchable player picker with pictures; `exclude` can never be chosen. */
export function PlayerSelect({
  players,
  value,
  onChange,
  exclude,
  ...rest
}: {
  players: PickPlayer[];
  value: number | null;
  onChange: (id: number | null) => void;
  exclude?: number | null;
} & Omit<SelectProps, "value" | "onChange" | "data">) {
  const byId = new Map(players.map((p) => [String(p.id), p]));
  return (
    <Select
      searchable
      nothingFoundMessage="–"
      value={value ? String(value) : null}
      onChange={(v) => onChange(v ? Number(v) : null)}
      data={players.map((p) => ({ value: String(p.id), label: p.name, disabled: p.id === exclude }))}
      renderOption={({ option }) => {
        const p = byId.get(option.value)!;
        return (
          <Group gap="sm" wrap="nowrap">
            <PlayerAvatar name={p.name} src={p.avatar} size={28} />
            <div>
              <Text size="sm" fw={600}>{p.name}</Text>
              {p.elo !== undefined && <Text size="xs" c="dimmed">Elo {p.elo}</Text>}
            </div>
          </Group>
        );
      }}
      {...rest}
    />
  );
}

/** All results that are possible in "best of N": 3:0 … 0:3. */
export function validScores(bestOf: number): [number, number][] {
  const need = (bestOf + 1) / 2;
  const out: [number, number][] = [];
  for (let l = 0; l < need; l++) out.push([need, l]);
  for (let l = need - 1; l >= 0; l--) out.push([l, need]);
  return out;
}

/**
 * Result input that only allows valid results.
 * Up to "best of 7": one tap on a result chip (3:0 … 0:3).
 * Longer formats: pick the winner, then the loser's legs (0 … first-to − 1).
 */
export function ScoreChips({
  bestOf,
  scoreA,
  scoreB,
  onChange,
  names = ["A", "B"],
}: {
  bestOf: number;
  scoreA: number | null;
  scoreB: number | null;
  onChange: (a: number, b: number) => void;
  names?: [string, string];
}) {
  if (bestOf > 7) return <LongFormatScore bestOf={bestOf} scoreA={scoreA} scoreB={scoreB} onChange={onChange} names={names} />;
  const value = scoreA !== null && scoreB !== null ? `${scoreA}:${scoreB}` : "";
  return (
    <Chip.Group value={value} onChange={(v) => { const [a, b] = String(v).split(":").map(Number); onChange(a, b); }}>
      <Group gap={8} justify="center">
        {validScores(bestOf).map(([a, b]) => (
          <Chip key={`${a}:${b}`} value={`${a}:${b}`} size="lg" radius="md" variant="filled" color={a > b ? "brand" : "dart"} icon={null}>
            <Text fw={900} size="lg" className="num">{a} : {b}</Text>
          </Chip>
        ))}
      </Group>
    </Chip.Group>
  );
}

/** Red confirm dialog, then POST (Inertia) - for delete / disable actions. */
export function confirmPost({ title, body, confirm, cancel, url, color = "red", data = {} }: { title: string; body: ReactNode; confirm: string; cancel: string; url: string; color?: string; data?: Record<string, string> }) {
  modals.openConfirmModal({
    title: <Text fw={800}>{title}</Text>,
    children: <Text size="sm">{body}</Text>,
    labels: { confirm, cancel },
    confirmProps: { color },
    cancelProps: { variant: "filled", color: "gray" },
    // Keep the scroll position only when the action returns to the same page.
    onConfirm: () => router.post(url, data, { preserveScroll: (page) => page.url.split("?")[0] === window.location.pathname }),
  });
}

function LongFormatScore({
  bestOf,
  scoreA,
  scoreB,
  onChange,
  names,
}: {
  bestOf: number;
  scoreA: number | null;
  scoreB: number | null;
  onChange: (a: number, b: number) => void;
  names: [string, string];
}) {
  const need = (bestOf + 1) / 2;
  const winner = scoreA === need ? "a" : scoreB === need ? "b" : null;
  const loserLegs = winner === "a" ? scoreB ?? 0 : winner === "b" ? scoreA ?? 0 : 0;
  const set = (w: "a" | "b", l: number) => (w === "a" ? onChange(need, l) : onChange(l, need));
  return (
    <Stack gap="sm" align="center">
      <SegmentedControl
        fullWidth
        w="100%"
        value={winner ?? ""}
        onChange={(w) => set(w as "a" | "b", loserLegs)}
        data={[
          { value: "a", label: `🏆 ${names[0]}` },
          { value: "b", label: `🏆 ${names[1]}` },
        ]}
      />
      <NumberInput
        w={220}
        size="lg"
        min={0}
        max={need - 1}
        clampBehavior="strict"
        allowDecimal={false}
        disabled={!winner}
        value={loserLegs}
        onChange={(v) => winner && set(winner, Number(v) || 0)}
        styles={{ input: { textAlign: "center", fontWeight: 900 } }}
        leftSection={<Text size="sm" fw={800} className="num">{need} :</Text>}
        leftSectionWidth={56}
      />
      {winner && (
        <Text fw={900} fz={28} className="num">
          {scoreA} : {scoreB}
        </Text>
      )}
    </Stack>
  );
}
