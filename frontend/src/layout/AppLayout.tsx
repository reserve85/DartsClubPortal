import { Link, router, usePage } from "@inertiajs/react";
import {
  ActionIcon,
  AppShell,
  Badge,
  Box,
  Burger,
  Divider,
  Group,
  Image,
  Indicator,
  Menu,
  NavLink,
  ScrollArea,
  Stack,
  Text,
  Tooltip,
  UnstyledButton,
  useComputedColorScheme,
  useMantineColorScheme,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import {
  IconBell,
  IconChevronDown,
  IconInfoCircle,
  IconLayoutDashboard,
  IconLogout,
  IconMoon,
  IconSettings,
  IconSun,
} from "@tabler/icons-react";
import { useEffect, type ReactNode } from "react";
import { CookieNotice } from "../components/CookieNotice";
import { NavIcon } from "../components/icons";
import { PlayerAvatar } from "../components/PlayerAvatar";
import { useT } from "../i18n";
import type { SharedProps } from "../types";

function getCookie(name: string): string {
  return document.cookie.split("; ").find((c) => c.startsWith(`${name}=`))?.split("=")[1] ?? "";
}

function useFlashToasts() {
  const { flash } = usePage<SharedProps>().props;
  useEffect(() => {
    for (const m of flash?.messages ?? []) {
      const level = (m.tags || m.level || "").toString();
      const color = level.includes("error") ? "red" : level.includes("warning") ? "yellow" : level.includes("success") ? "green" : "brand";
      notifications.show({ message: m.message, color, autoClose: level.includes("error") ? 7000 : 3500 });
    }
  }, [flash]);
}

/** Club logo (dark/light variant) - else the dart badge. */
function ClubLogo() {
  const { site } = usePage<SharedProps>().props;
  const scheme = useComputedColorScheme("dark");
  const src = scheme === "dark" ? site.logo?.dark || site.logo?.light : site.logo?.light || site.logo?.dark;
  if (src) return <Image src={src} h={36} w="auto" maw={140} fit="contain" alt={site.name} />;
  return (
    <Box
      w={32}
      h={32}
      style={{
        borderRadius: 9,
        display: "grid",
        placeItems: "center",
        background: "linear-gradient(135deg, var(--mantine-color-brand-6), var(--mantine-color-dart-6))",
      }}
    >
      🎯
    </Box>
  );
}

function ThemeToggle() {
  const { setColorScheme } = useMantineColorScheme();
  const computed = useComputedColorScheme("dark");
  const t = useT();
  const next = computed === "dark" ? "light" : "dark";
  return (
    <Tooltip label={computed === "dark" ? t("Light mode") : t("Dark mode")}>
      <ActionIcon
        variant="default"
        size="lg"
        aria-label={t("Switch colour scheme")}
        onClick={() => {
          setColorScheme(next);
          const body = new URLSearchParams({ theme: next });
          fetch("/accounts/settings/theme/", {
            method: "POST",
            headers: { "X-CSRFToken": decodeURIComponent(getCookie("csrftoken")) },
            body,
          });
        }}
      >
        {computed === "dark" ? <IconSun size={18} /> : <IconMoon size={18} />}
      </ActionIcon>
    </Tooltip>
  );
}

export default function AppLayout({ children }: { children: ReactNode }) {
  const page = usePage<SharedProps>();
  const { auth, nav, site, urls, counts } = page.props;
  const user = auth.user;
  const t = useT();
  const [opened, { toggle, close }] = useDisclosure(false);
  useFlashToasts();
  useEffect(() => router.on("navigate", () => close()), [close]);

  // Longest matching menu link is the active one.
  const path = page.url.split("?")[0];
  const allHrefs = nav.flatMap((g) => g.items.map((i) => i.href)).concat(urls.overview ? [urls.overview] : []);
  const active = allHrefs.filter((h) => path === h || (h !== "/" && path.startsWith(h))).sort((a, b) => b.length - a.length)[0];
  const showOverview = Boolean(user?.modules.elo && user?.modules.penalty && urls.overview);

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{ width: 268, breakpoint: "md", collapsed: { mobile: !opened } }}
      padding={{ base: "sm", sm: "md" }}
    >
      <AppShell.Header>
        <Group h={57} px="md" justify="space-between" wrap="nowrap">
          <Group gap="xs" wrap="nowrap">
            <Burger opened={opened} onClick={toggle} hiddenFrom="md" size="sm" aria-label={t("Menu")} />
            <UnstyledButton component={Link} href={urls.home ?? "/"}>
              <Group gap={8} wrap="nowrap">
                <ClubLogo />
                <Text fw={800} size="lg" visibleFrom="xs" truncate>
                  {site.name}
                </Text>
              </Group>
            </UnstyledButton>
          </Group>
          {user && (
            <Group gap={8} wrap="nowrap">
              <ThemeToggle />
              <Tooltip label={t("Notifications")}>
                <Indicator disabled={!counts.notifications} label={counts.notifications} size={16} color="dart" offset={4}>
                  <ActionIcon variant="default" size="lg" component={Link} href={urls.notifications ?? "#"} aria-label={t("Notifications")}>
                    <IconBell size={18} />
                  </ActionIcon>
                </Indicator>
              </Tooltip>
              <Menu position="bottom-end" width={240}>
                <Menu.Target>
                  <UnstyledButton aria-label={t("Account")}>
                    <Group gap={6} wrap="nowrap">
                      <PlayerAvatar name={user.name} src={user.avatar} size={34} />
                      <IconChevronDown size={14} />
                    </Group>
                  </UnstyledButton>
                </Menu.Target>
                <Menu.Dropdown>
                  <Menu.Label>
                    <Text size="sm" fw={700} c="var(--mantine-color-text)" truncate>{user.name}</Text>
                    <Text size="xs" c="dimmed" truncate>{user.email}</Text>
                    <Group gap={4} mt={6}>
                      <Badge size="xs" color={user.isAdmin ? "dart" : "gray"}>{user.role === "system" ? "System" : user.isAdmin ? t("Admin") : t("User")}</Badge>
                      {user.captainOf && <Badge size="xs" color="brand">{t("Captain")} · {user.captainOf.name}</Badge>}
                    </Group>
                  </Menu.Label>
                  <Menu.Divider />
                  <Menu.Item component={Link} href={urls.settings ?? "#"} leftSection={<IconSettings size={16} />}>{t("Settings")}</Menu.Item>
                  {urls.rights && <Menu.Item component={Link} href={urls.rights} leftSection={<IconInfoCircle size={16} />}>{t("Who may do what?")}</Menu.Item>}
                  <Menu.Divider />
                  <Menu.Item color="red" leftSection={<IconLogout size={16} />} onClick={() => router.post(urls.logout ?? "/accounts/logout/")}>
                    {t("Logout")}
                  </Menu.Item>
                </Menu.Dropdown>
              </Menu>
            </Group>
          )}
        </Group>
        <div className="brand-line" />
      </AppShell.Header>

      {user && (
        <AppShell.Navbar p="sm">
          <AppShell.Section grow component={ScrollArea} type="never">
            <Stack gap={4}>
              {showOverview && (
                <NavLink
                  component={Link}
                  href={urls.overview!}
                  label={t("My overview")}
                  leftSection={<IconLayoutDashboard size={18} />}
                  active={active === urls.overview}
                  variant="filled"
                  style={{ borderRadius: 10 }}
                />
              )}
              {nav.map((group) => (
                <Box key={group.key} mt="sm">
                  <Group gap={6} px="xs" mb={4} justify="space-between" wrap="nowrap">
                    <Group gap={6} wrap="nowrap">
                      <NavIcon name={group.icon} size={14} />
                      <Text size="xs" fw={800} tt="uppercase" c="dimmed" style={{ letterSpacing: ".06em" }}>{group.label}</Text>
                    </Group>
                    {group.hint && <Badge size="xs" variant="light">{group.hint}</Badge>}
                  </Group>
                  {group.items.map((item) => (
                    <NavLink
                      key={item.href}
                      component={Link}
                      href={item.href}
                      label={item.label}
                      leftSection={<NavIcon name={item.icon} />}
                      active={active === item.href}
                      variant="filled"
                      style={{ borderRadius: 10 }}
                      rightSection={
                        item.href === "/accounts/users/" && counts.approvals ? <Badge size="sm" color="dart" variant="filled">{counts.approvals}</Badge> : null
                      }
                    />
                  ))}
                </Box>
              ))}
            </Stack>
          </AppShell.Section>
          <AppShell.Section>
            <Divider my="xs" />
            <Group gap="xs" px="xs" justify="space-between">
              <Text size="xs" c="dimmed" component={Link} href={urls.imprint ?? "#"}>{t("Imprint")}</Text>
              <Text size="xs" c="dimmed" component={Link} href={urls.privacy ?? "#"}>{t("Privacy Policy")}</Text>
            </Group>
          </AppShell.Section>
        </AppShell.Navbar>
      )}

      <AppShell.Main>
        <Box maw={1100} mx="auto" pb={96}>{children}</Box>
      </AppShell.Main>
      <CookieNotice />
    </AppShell>
  );
}
