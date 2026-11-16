import { Badge, Box, Group, Paper, SimpleGrid, Stack, Text, Title, type MantineColor } from "@mantine/core";
import { IconTrendingDown, IconTrendingUp } from "@tabler/icons-react";
import type { ReactNode } from "react";
import { useFormat } from "../i18n";

/** Page title band (same on every page). */
export function PageHeader({
  title,
  subtitle,
  left,
  actions,
  children,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  left?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <Paper className="hero" withBorder p={{ base: "md", sm: "lg" }} mb="md">
      <Group justify="space-between" align="center" wrap="wrap" gap="sm">
        <Group gap="md" wrap="nowrap" style={{ minWidth: 0, flex: "1 1 14rem" }}>
          {left}
          <Box style={{ minWidth: 0 }}>
            <Title order={1} fz={{ base: 22, sm: 26 }} lh={1.15}>
              {title}
            </Title>
            {subtitle && (
              <Text size="sm" c="dimmed" mt={4}>
                {subtitle}
              </Text>
            )}
          </Box>
        </Group>
        {actions && <Group gap="xs">{actions}</Group>}
      </Group>
      {children && <Box mt="md">{children}</Box>}
    </Paper>
  );
}

export function StatTile({ label, value, color }: { label: string; value: ReactNode; color?: MantineColor }) {
  return (
    <Paper withBorder p="sm" radius="md" ta="center">
      <Text size="xs" tt="uppercase" fw={700} c="dimmed" style={{ letterSpacing: ".05em" }}>
        {label}
      </Text>
      <Text fw={800} fz={22} c={color} className="num" mt={2}>
        {value}
      </Text>
    </Paper>
  );
}

export function StatGrid({ children }: { children: ReactNode }) {
  return <SimpleGrid cols={3} spacing="xs">{children}</SimpleGrid>;
}

/** Elo change: green up / red down / grey ±0. */
export function Delta({ value, digits = 1, size = "sm" }: { value: number; digits?: number; size?: string }) {
  const f = useFormat();
  if (Math.abs(value) < 0.05)
    return <Text span size={size} c="dimmed" fw={700} className="num">±0</Text>;
  const up = value > 0;
  return (
    <Text span size={size} fw={800} c={up ? "teal" : "red"} className="num" style={{ whiteSpace: "nowrap" }}>
      {up ? <IconTrendingUp size={14} style={{ verticalAlign: -2 }} /> : <IconTrendingDown size={14} style={{ verticalAlign: -2 }} />}{" "}
      {f.signed(value, digits)}
    </Text>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <Paper withBorder p="xl" ta="center">
      <Text c="dimmed">{children}</Text>
    </Paper>
  );
}

export function Section({ title, right, children }: { title: ReactNode; right?: ReactNode; children: ReactNode }) {
  return (
    <Stack gap="xs" mt="lg">
      <Group justify="space-between">
        <Text size="xs" fw={800} tt="uppercase" c="dimmed" style={{ letterSpacing: ".06em" }}>
          {title}
        </Text>
        {right}
      </Group>
      {children}
    </Stack>
  );
}

export function ReadOnlyBadge({ label }: { label: string }) {
  return <Badge color="gray" variant="outline">{label}</Badge>;
}
