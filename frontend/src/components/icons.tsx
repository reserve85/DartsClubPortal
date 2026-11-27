import {
  IconAdjustments,
  IconBook,
  IconCalendar,
  IconCalendarCog,
  IconCalendarEvent,
  IconCash,
  IconCoins,
  IconCrown,
  IconFlag,
  IconHistory,
  IconLayoutDashboard,
  IconList,
  IconPlus,
  IconShield,
  IconSwords,
  IconTarget,
  IconTrophy,
  IconUpload,
  IconUserCog,
  IconUsers,
  IconUsersGroup,
  IconWallet,
  IconPhoto,
  type Icon,
} from "@tabler/icons-react";

/** Icon names used by the server-built menu (app/core/inertia_share.py). */
export const ICONS: Record<string, Icon> = {
  adjustments: IconAdjustments,
  book: IconBook,
  calendar: IconCalendar,
  "calendar-cog": IconCalendarCog,
  "calendar-event": IconCalendarEvent,
  cash: IconCash,
  coins: IconCoins,
  crown: IconCrown,
  flag: IconFlag,
  history: IconHistory,
  overview: IconLayoutDashboard,
  list: IconList,
  plus: IconPlus,
  shield: IconShield,
  swords: IconSwords,
  target: IconTarget,
  trophy: IconTrophy,
  upload: IconUpload,
  "user-cog": IconUserCog,
  users: IconUsers,
  "users-group": IconUsersGroup,
  wallet: IconWallet,
  photo: IconPhoto,
};

export function NavIcon({ name, size = 18 }: { name: string; size?: number }) {
  const C = ICONS[name] ?? IconList;
  return <C size={size} stroke={1.8} />;
}
