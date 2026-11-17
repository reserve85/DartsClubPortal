import { Chip, Group, Select, SimpleGrid, Text, type SelectProps } from "@mantine/core";
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

/**
 * Result input that only allows valid results - one tap, for every format.
 * Left column: the left player won (3:0, 3:1, 3:2), right column: the right
 * player won (0:3, 1:3, 2:3); each row pairs the mirrored results.
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
  const need = (bestOf + 1) / 2;
  const value = scoreA !== null && scoreB !== null ? `${scoreA}:${scoreB}` : "";
  const chip = (a: number, b: number) => (
    <Chip key={`${a}:${b}`} value={`${a}:${b}`} size="lg" radius="md" variant="filled" color={a > b ? "brand" : "dart"} icon={null} styles={{ root: { width: "100%" }, label: { width: "100%", justifyContent: "center" } }}>
      <Text fw={900} size="lg" className="num">{a} : {b}</Text>
    </Chip>
  );
  return (
    <Chip.Group value={value} onChange={(v) => { const [a, b] = String(v).split(":").map(Number); onChange(a, b); }}>
      <SimpleGrid cols={2} spacing={8} verticalSpacing={8} maw={360} mx="auto">
        {names.map((name, i) => (
          <Text key={i} size="sm" fw={700} ta="center" truncate>🏆 {name}</Text>
        ))}
        {Array.from({ length: need }, (_, loser) => [chip(need, loser), chip(loser, need)])}
      </SimpleGrid>
    </Chip.Group>
  );
}

/** Red confirm dialog, then POST (Inertia) - for delete / disable actions. */
export function confirmPost({ title, body, confirm, cancel, url, color = "red", data = {} }: { title: string; body: ReactNode; confirm: string; cancel: string; url: string; color?: string; data?: Record<string, string> }) {
  modals.openConfirmModal({
    modalId: "confirm", // one at a time: a double tap must not stack a second dialog
    title: <Text fw={800}>{title}</Text>,
    children: <Text size="sm">{body}</Text>,
    labels: { confirm, cancel },
    confirmProps: { color },
    cancelProps: { variant: "filled", color: "gray" },
    // Keep the scroll position only when the action returns to the same page.
    onConfirm: () => router.post(url, data, { preserveScroll: (page) => page.url.split("?")[0] === window.location.pathname }),
  });
}
