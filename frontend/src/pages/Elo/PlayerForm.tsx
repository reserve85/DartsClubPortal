import { Head, Link, useForm } from "@inertiajs/react";
import { Alert, Button, Group, NumberInput, Paper, Select, SimpleGrid, Stack, TextInput } from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { IconAlertTriangle } from "@tabler/icons-react";
import dayjs from "dayjs";
import { AvatarUpload } from "../../components/AvatarUpload";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { PageHeader } from "../../components/ui";
import { useFormat, useT } from "../../i18n";

interface Props {
  mode: "add" | "edit";
  persons?: { id: number; name: string }[];
  defaults?: { startElo: number; entryDate: string };
  player?: { id: number; name: string; avatar: string; startElo: number; entryDate: string; firstMatch: string | null };
  today: string;
  errors: Record<string, string>;
}

export default function PlayerForm({ mode, persons = [], defaults, player, today, errors }: Props) {
  const t = useT();
  const f = useFormat();
  const edit = mode === "edit" && player;
  const form = useForm({
    existing: "" as string,
    name: edit ? player.name : "",
    start_elo: edit ? player.startElo : defaults?.startElo ?? 1200,
    entry_date: edit ? player.entryDate : defaults?.entryDate ?? today,
  });
  const d = form.data;
  const url = edit ? `/elo/manage/players/${player.id}/edit/` : "/elo/manage/players/add/";
  return (
    <>
      <Head title={edit ? t("Edit Elo player") : t("Add player")} />
      <PageHeader
        left={edit ? <PlayerAvatar name={player.name} src={player.avatar} size={56} /> : undefined}
        title={edit ? player.name : t("Add player to the Elo ranking")}
        subtitle={edit ? t("Edit Elo player") : undefined}
      />
      <Paper withBorder p="md" maw={760}>
        <form onSubmit={(e) => { e.preventDefault(); form.post(url); }}>
          <Stack>
            {errors.form && <Alert color="red" icon={<IconAlertTriangle />}>{errors.form}</Alert>}
            {!edit && (
              <Select
                label={t("Existing person")}
                description={t("Pick a person who is already in the club portal (e.g. from the penalty module).")}
                placeholder={t("— new person —")}
                data={persons.map((p) => ({ value: String(p.id), label: p.name }))}
                value={d.existing || null}
                onChange={(v) => form.setData((p) => ({ ...p, existing: v ?? "", name: v ? "" : p.name }))}
                searchable
                clearable
                allowDeselect
              />
            )}
            {(edit || !d.existing) && (
              <TextInput label={t("Name")} value={d.name} onChange={(e) => form.setData("name", e.currentTarget.value)} error={errors.name} required maxLength={120} />
            )}
            <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="md">
            <NumberInput
              label={t("Start Elo")}
              description={edit ? t("Changing it recalculates every match of this player.") : undefined}
              min={100}
              max={4000}
              allowDecimal={false}
              clampBehavior="strict"
              value={d.start_elo}
              onChange={(v) => form.setData("start_elo", Number(v) || 0)}
              error={errors.start_elo}
            />
            <DatePickerInput
              label={t("Entry date")}
              description={
                edit && player.firstMatch
                  ? `${t("The player is part of the ranking from this day on.")} (≤ ${f.date(player.firstMatch)})`
                  : t("The player is part of the ranking from this day on.")
              }
              value={d.entry_date}
              maxDate={edit && player.firstMatch ? player.firstMatch : today}
              onChange={(v) => form.setData("entry_date", v ? dayjs(v).format("YYYY-MM-DD") : d.entry_date)}
              error={errors.entry_date}
            />
            </SimpleGrid>
            <Group>
              <Button type="submit" loading={form.processing}>{edit ? t("Save changes") : t("Add player")}</Button>
              <Button color="gray" component={Link} href="/elo/manage/">{t("Cancel")}</Button>
            </Group>
          </Stack>
        </form>
      </Paper>
      {edit && <AvatarUpload playerId={player.id} name={player.name} avatar={player.avatar} />}
    </>
  );
}
