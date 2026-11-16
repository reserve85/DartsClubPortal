import { router } from "@inertiajs/react";
import { Chip, Group, Stack, Switch } from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import dayjs from "dayjs";
import { useState } from "react";
import { useT } from "../i18n";

export interface Period {
  key: string;
  from: string;
  to: string;
}

/**
 * Period chips (month / last month / year / all / custom range) and the
 * optional "show inactive" switch. Changes reload ONLY the page data
 * (Inertia partial visit, scroll position kept) - no full page load.
 */
export function PeriodFilter({
  period,
  today,
  includeInactive,
  showInactiveSwitch = true,
}: {
  period: Period;
  today: string;
  includeInactive?: boolean;
  showInactiveSwitch?: boolean;
}) {
  const t = useT();
  const [range, setRange] = useState<[string | null, string | null]>([period.from, period.to]);
  const visit = (params: Record<string, string>) =>
    router.get(window.location.pathname, { ...params, inactive: includeInactive === false ? "0" : "1" }, { preserveScroll: true, preserveState: true, replace: true });

  return (
    <Stack gap="sm">
      <Chip.Group
        value={period.key}
        onChange={(key) => {
          const k = key as string;
          if (k === "custom") visit({ period: "custom", from: period.from, to: period.to });
          else visit({ period: k });
        }}
      >
        <Group gap={6}>
          {[
            ["month", t("This month")],
            ["last_month", t("Last month")],
            ["year", t("This year")],
            ["all", t("All time")],
            ["custom", t("Custom")],
          ].map(([value, label]) => (
            <Chip key={value} value={value} size="sm" variant="filled" radius="xl">
              {label}
            </Chip>
          ))}
        </Group>
      </Chip.Group>
      {period.key === "custom" && (
        <DatePickerInput
          type="range"
          label={t("Period")}
          value={range}
          maxDate={today}
          allowSingleDateInRange
          onChange={(value) => {
            setRange(value as [string | null, string | null]);
            const [a, b] = value as [string | null, string | null];
            if (a && b) visit({ period: "custom", from: dayjs(a).format("YYYY-MM-DD"), to: dayjs(b).format("YYYY-MM-DD") });
          }}
          maw={340}
        />
      )}
      {showInactiveSwitch && (
        <Group>
          <Switch
            checked={includeInactive}
            label={t("Show inactive and disabled players")}
            onChange={(e) =>
              router.get(
                window.location.pathname,
                { period: period.key, from: period.from, to: period.to, inactive: e.currentTarget.checked ? "1" : "0" },
                { preserveScroll: true, preserveState: true, replace: true },
              )
            }
          />
        </Group>
      )}
    </Stack>
  );
}
