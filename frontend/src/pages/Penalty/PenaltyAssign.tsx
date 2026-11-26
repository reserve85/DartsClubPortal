import { Head, Link, useForm } from "@inertiajs/react";
import { Alert, Badge, Box, Button, Group, NumberInput, Paper, Select, SimpleGrid, Stack, Text, TextInput, UnstyledButton } from "@mantine/core";
import { IconAlertTriangle, IconCheck, IconUsersGroup } from "@tabler/icons-react";
import type { ReactNode } from "react";
import { PlayerAvatar } from "../../components/PlayerAvatar";
import { PageHeader, Section } from "../../components/ui";
import { useFormat, useT } from "../../i18n";

interface Item {
  id: number;
  description: string;
  amount: number;
  manual: boolean;
  group: boolean;
  both: boolean;
}
interface Person {
  id: number;
  name: string;
  avatar: string;
}
interface Props {
  matchday: { id: number; label: string; team: string; date: string };
  items: Item[];
  players: Person[];
  values: Record<string, string>;
  errors: Record<string, string>;
}

/** A big tappable tile; selected = filled border + check mark. */
function Pick({ on, onClick, children, disabled }: { on: boolean; onClick: () => void; children: ReactNode; disabled?: boolean }) {
  return (
    <UnstyledButton onClick={onClick} disabled={disabled} aria-pressed={on} style={{ opacity: disabled ? 0.4 : 1 }}>
      <Paper
        withBorder
        p="sm"
        radius="md"
        h="100%"
        bg={on ? "var(--mantine-color-brand-light)" : undefined}
        style={{ borderColor: on ? "var(--mantine-color-brand-filled)" : undefined, borderWidth: on ? 2 : 1, position: "relative" }}
      >
        {on && (
          <Box pos="absolute" top={6} right={8} c="brand">
            <IconCheck size={16} />
          </Box>
        )}
        {children}
      </Paper>
    </UnstyledButton>
  );
}

export default function PenaltyAssign({ matchday, items, players, values, errors }: Props) {
  const t = useT();
  const f = useFormat();
  const form = useForm({
    catalog_item: values.catalog_item ?? "",
    player: values.player ?? "",
    double_partner: values.double_partner ?? "",
    amount_eur: values.amount_eur ?? "",
    description: values.description ?? "",
  });
  const d = form.data;
  const item = items.find((i) => String(i.id) === d.catalog_item);
  const set = (k: keyof typeof d, v: string) => form.setData((p) => ({ ...p, [k]: v }));
  const ready = item && d.player && (!item.manual || (Number(d.amount_eur) > 0 && d.description.trim()));
  return (
    <>
      <Head title={t("Add penalty")} />
      <PageHeader title={t("Add penalty")} subtitle={matchday.label} />
      <form
        style={{ maxWidth: 760 }}
        onSubmit={(e) => {
          e.preventDefault();
          form.transform((data) => ({ ...data, double_partner: item?.both ? data.double_partner : "", amount_eur: item?.manual ? data.amount_eur : "" }));
          form.post(`/matchdays/${matchday.id}/penalties/add/`, { preserveScroll: "errors" });
        }}
      >
        <Stack gap="md">
          {errors.form && <Alert color="red" icon={<IconAlertTriangle />}>{errors.form}</Alert>}
          {players.length === 0 && (
            <Alert color="yellow" icon={<IconAlertTriangle />}>
              {t("This matchday has no participants yet.")}{" "}
              <Text component={Link} href={`/matchdays/${matchday.id}/`} fw={700} c="inherit" td="underline">{t("Add players")}</Text>
            </Alert>
          )}

          <Section title={`1 · ${t("Penalty type")}`}>
            <Select
              placeholder={t("Choose a penalty type")}
              data={items.map((i) => ({ value: String(i.id), label: i.manual ? `${i.description} (${t("individual")})` : `${i.description} (${f.euro(i.amount)})` }))}
              value={d.catalog_item || null}
              onChange={(v) => set("catalog_item", v ?? "")}
              searchable={items.length > 8}
              nothingFoundMessage="—"
              size="md"
              maxDropdownHeight={360}
              error={errors.catalog_item}
              renderOption={({ option, checked }) => {
                const i = items.find((x) => String(x.id) === option.value)!;
                return (
                  <Group justify="space-between" wrap="nowrap" w="100%" gap="xs">
                    <Group gap={6} wrap="nowrap" style={{ minWidth: 0 }}>
                      {checked && <IconCheck size={14} />}
                      <Text size="sm" fw={600} truncate>{i.description}</Text>
                      {i.group && <Badge size="xs" color="grape" variant="light">{t("group")}</Badge>}
                      {i.both && <Badge size="xs" color="cyan" variant="light">{t("doubles")}</Badge>}
                    </Group>
                    <Text size="sm" fw={800} c={i.manual ? "dimmed" : "red"} className="num" style={{ flexShrink: 0 }}>
                      {i.manual ? t("individual") : f.euro(i.amount)}
                    </Text>
                  </Group>
                );
              }}
            />
          </Section>

          {item?.group && (
            <Alert color="grape" icon={<IconUsersGroup />}>
              {t("Group penalty: every OTHER participant of the matchday pays. Pick the player who triggered it.")}
            </Alert>
          )}

          <Section title={`2 · ${item?.group ? t("Triggered by") : t("Player")}`}>
            <SimpleGrid cols={{ base: 2, xs: 3, sm: 4 }} spacing="xs">
              {players.map((p) => (
                <Pick key={p.id} on={d.player === String(p.id)} onClick={() => form.setData((x) => ({ ...x, player: String(p.id), double_partner: x.double_partner === String(p.id) ? "" : x.double_partner }))}>
                  <Group gap="xs" wrap="nowrap">
                    <PlayerAvatar name={p.name} src={p.avatar} size={30} />
                    <Text size="sm" fw={600} truncate pr={14}>{p.name}</Text>
                  </Group>
                </Pick>
              ))}
            </SimpleGrid>
            {errors.player && <Text c="red" size="sm" mt={6}>{errors.player}</Text>}
          </Section>

          {item?.both && (
            <Section title={t("Doubles partner (optional)")}>
              <SimpleGrid cols={{ base: 2, xs: 3, sm: 4 }} spacing="xs">
                {players.map((p) => (
                  <Pick key={p.id} disabled={d.player === String(p.id)} on={d.double_partner === String(p.id)} onClick={() => set("double_partner", d.double_partner === String(p.id) ? "" : String(p.id))}>
                    <Group gap="xs" wrap="nowrap">
                      <PlayerAvatar name={p.name} src={p.avatar} size={30} />
                      <Text size="sm" fw={600} truncate pr={14}>{p.name}</Text>
                    </Group>
                  </Pick>
                ))}
              </SimpleGrid>
              {errors.double_partner && <Text c="red" size="sm" mt={6}>{errors.double_partner}</Text>}
            </Section>
          )}

          <Paper withBorder p="md">
            <Stack gap="sm">
              {item?.manual && (
                <NumberInput
                  label={t("Amount (EUR)")}
                  required
                  min={0.01}
                  max={9999}
                  decimalScale={2}
                  fixedDecimalScale
                  decimalSeparator={f.decimalSeparator}
                  step={0.5}
                  clampBehavior="strict"
                  value={d.amount_eur === "" ? "" : Number(d.amount_eur)}
                  onChange={(v) => set("amount_eur", v === "" ? "" : String(v))}
                  error={errors.amount_eur}
                  rightSection={<Text size="sm" c="dimmed">€</Text>}
                />
              )}
              <TextInput
                label={item?.manual ? t("Comment / reason") : t("Comment (optional)")}
                description={t("Shown behind the penalty type, e.g. Late arrival (9 points).")}
                required={item?.manual}
                maxLength={255}
                value={d.description}
                onChange={(e) => set("description", e.currentTarget.value)}
                error={errors.description}
              />
              <Group gap="sm" mt="xs">
                <Button type="submit" disabled={!ready} loading={form.processing}>
                  {item?.group ? t("Assign group penalty") : t("Assign penalty")}
                </Button>
                <Button color="gray" component={Link} href={`/matchdays/${matchday.id}/`}>{t("Cancel")}</Button>
              </Group>
            </Stack>
          </Paper>
        </Stack>
      </form>
    </>
  );
}
