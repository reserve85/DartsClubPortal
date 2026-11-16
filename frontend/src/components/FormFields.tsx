import {
  Chip,
  Group,
  MultiSelect,
  NumberInput,
  PasswordInput,
  Radio,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  Textarea,
  TextInput,
} from "@mantine/core";
import { DatePickerInput, TimeInput } from "@mantine/dates";
import { usePage } from "@inertiajs/react";
import dayjs from "dayjs";
import type { ReactNode } from "react";

/** One Django form field as described by app/core/inertia_utils.form_schema. */
export interface FieldDef {
  name: string;
  type:
    | "text" | "email" | "password" | "textarea" | "number" | "select" | "multiselect"
    | "radio" | "switch" | "date" | "datetime" | "time" | "file" | "hidden";
  label: string;
  help: string;
  required: boolean;
  disabled: boolean;
  value: unknown;
  error: string;
  placeholder?: string;
  maxLength?: number;
  choices?: { value: string; label: string }[];
  min?: number | string;
  max?: number | string;
  step?: number;
  decimals?: number;
}

export type FormData = Record<string, unknown>;

/** Initial form state: every editable field with its current value. */
export function initialData(fields: FieldDef[]): FormData {
  return Object.fromEntries(
    fields.filter((f) => !f.disabled && f.type !== "file").map((f) => [f.name, f.value]),
  );
}

function FieldLabel({ field }: { field: FieldDef }) {
  if (!field.label) return null;
  return (
    <Text size="sm" fw={500}>
      {field.label}
      {field.required && <Text span c="red"> *</Text>}
    </Text>
  );
}

export function Field({
  field,
  value,
  onChange,
  error,
}: {
  field: FieldDef;
  value: unknown;
  onChange: (v: unknown) => void;
  error?: string;
}) {
  const common = {
    label: field.label || undefined,
    description: field.help || undefined,
    required: field.required,
    disabled: field.disabled,
    error: error || field.error || undefined,
  };
  const choices = field.choices ?? [];
  const comma = usePage<{ site?: { language: string } }>().props.site?.language !== "en";
  switch (field.type) {
    case "hidden":
    case "file":
      return null;
    case "switch":
      return (
        <Switch
          label={field.label}
          description={field.help || undefined}
          disabled={field.disabled}
          error={common.error}
          checked={Boolean(value)}
          onChange={(e) => onChange(e.currentTarget.checked)}
          size="md"
        />
      );
    case "textarea":
      return (
        <Textarea
          {...common}
          autosize
          minRows={2}
          maxRows={8}
          maxLength={field.maxLength}
          placeholder={field.placeholder}
          value={String(value ?? "")}
          onChange={(e) => onChange(e.currentTarget.value)}
        />
      );
    case "password":
      return (
        <PasswordInput
          {...common}
          value={String(value ?? "")}
          autoComplete="new-password"
          onChange={(e) => onChange(e.currentTarget.value)}
        />
      );
    case "number":
      return (
        <NumberInput
          {...common}
          placeholder={field.placeholder}
          value={value === null || value === undefined ? "" : (value as number)}
          min={typeof field.min === "number" ? field.min : undefined}
          max={typeof field.max === "number" ? field.max : undefined}
          step={field.step ?? 1}
          decimalScale={field.decimals ?? undefined}
          fixedDecimalScale={field.decimals === 2}
          decimalSeparator={comma ? "," : "."}
          allowDecimal={field.decimals !== 0}
          clampBehavior="strict"
          onChange={(v) => onChange(v === "" ? null : Number(v))}
        />
      );
    case "select":
      return (
        <Select
          {...common}
          data={choices}
          value={value ? String(value) : null}
          placeholder={field.placeholder ?? (field.required ? undefined : "—")}
          searchable={choices.length > 8}
          clearable={!field.required}
          allowDeselect={!field.required}
          nothingFoundMessage="—"
          onChange={(v) => onChange(v ?? "")}
        />
      );
    case "multiselect":
      if (choices.length <= 12)
        return (
          <Stack gap={6}>
            <FieldLabel field={field} />
            {field.help && <Text size="xs" c="dimmed">{field.help}</Text>}
            <Chip.Group multiple value={(value as string[]) ?? []} onChange={onChange}>
              <Group gap={6}>
                {choices.map((c) => (
                  <Chip key={c.value} value={c.value} disabled={field.disabled} variant="filled">
                    {c.label}
                  </Chip>
                ))}
              </Group>
            </Chip.Group>
            {common.error && <Text size="xs" c="red">{common.error}</Text>}
          </Stack>
        );
      return (
        <MultiSelect
          {...common}
          data={choices}
          value={(value as string[]) ?? []}
          searchable
          hidePickedOptions
          onChange={onChange}
        />
      );
    case "radio":
      if (choices.length <= 4 && choices.every((c) => c.label.length < 18))
        return (
          <Stack gap={4}>
            <FieldLabel field={field} />
            <SegmentedControl
              fullWidth
              data={choices}
              value={String(value ?? "")}
              disabled={field.disabled}
              onChange={onChange}
            />
            {field.help && <Text size="xs" c="dimmed">{field.help}</Text>}
            {common.error && <Text size="xs" c="red">{common.error}</Text>}
          </Stack>
        );
      return (
        <Radio.Group {...common} value={String(value ?? "")} onChange={onChange}>
          <Stack gap={6} mt={6}>
            {choices.map((c) => (
              <Radio key={c.value} value={c.value} label={c.label} />
            ))}
          </Stack>
        </Radio.Group>
      );
    case "date":
    case "datetime":
      return (
        <DatePickerInput
          {...common}
          value={value ? String(value).slice(0, 10) : null}
          minDate={typeof field.min === "string" ? field.min : undefined}
          maxDate={typeof field.max === "string" ? field.max : undefined}
          clearable={!field.required}
          onChange={(v) => onChange(v ? dayjs(v).format("YYYY-MM-DD") : "")}
        />
      );
    case "time":
      return (
        <TimeInput {...common} value={String(value ?? "")} onChange={(e) => onChange(e.currentTarget.value)} />
      );
    default:
      return (
        <TextInput
          {...common}
          type={field.type === "email" ? "email" : "text"}
          placeholder={field.placeholder}
          maxLength={field.maxLength}
          value={String(value ?? "")}
          onChange={(e) => onChange(e.currentTarget.value)}
        />
      );
  }
}

/**
 * Renders a whole Django form. ``rows`` optionally puts several fields side by
 * side (e.g. [["date", "venue"]]); fields not mentioned get their own row.
 * ``render`` may replace single fields with a custom control.
 */
export function FormFields({
  fields,
  data,
  setData,
  errors = {},
  rows = [],
  render,
}: {
  fields: FieldDef[];
  data: FormData;
  setData: (name: string, value: unknown) => void;
  errors?: Record<string, string>;
  rows?: string[][];
  render?: (field: FieldDef) => ReactNode | undefined;
}) {
  const byName = new Map(fields.map((f) => [f.name, f]));
  const placed = new Set<string>();
  const blocks: ReactNode[] = [];
  const one = (f: FieldDef) => {
    const custom = render?.(f);
    if (custom !== undefined) return custom;
    return (
      <Field
        field={f}
        value={f.disabled ? f.value : data[f.name]}
        onChange={(v) => setData(f.name, v)}
        error={errors[f.name]}
      />
    );
  };
  for (const f of fields) {
    if (placed.has(f.name) || f.type === "hidden") continue;
    const row = rows.find((r) => r.includes(f.name));
    if (row) {
      const members = row.map((n) => byName.get(n)).filter(Boolean) as FieldDef[];
      members.forEach((m) => placed.add(m.name));
      blocks.push(
        <SimpleGrid key={row.join("+")} cols={{ base: 1, xs: members.length }} spacing="md">
          {members.map((m) => (
            <div key={m.name}>{one(m)}</div>
          ))}
        </SimpleGrid>,
      );
    } else {
      placed.add(f.name);
      blocks.push(<div key={f.name}>{one(f)}</div>);
    }
  }
  return <Stack gap="md">{blocks}</Stack>;
}
