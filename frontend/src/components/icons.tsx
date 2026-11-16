import {
  IconAdjustments,
  IconBook,
  IconCalendar,
  IconCalendarCog,
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
  wallet: IconWallet,
  photo: IconPhoto,
};

export function NavIcon({ name, size = 18 }: { name: string; size?: number }) {
  const C = ICONS[name] ?? IconList;
  return <C size={size} stroke={1.8} />;
}
