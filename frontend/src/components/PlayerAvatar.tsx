import { Avatar, type AvatarProps } from "@mantine/core";
import { colorFor } from "../theme";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  const first = Array.from(parts[0])[0] ?? "";
  const last = parts.length > 1 ? Array.from(parts[parts.length - 1])[0] ?? "" : Array.from(parts[0])[1] ?? "";
  return (first + last).toUpperCase();
}

/** Round avatar: uploaded picture, else initials in the person's colour. */
export function PlayerAvatar({ name, src, muted, ...rest }: { name: string; src?: string | null; muted?: boolean } & AvatarProps) {
  return (
    <Avatar
      src={src || null}
      alt={name}
      color={muted ? "gray" : colorFor(name)}
      variant="filled"
      radius={9999} // always a circle, whatever the size
      {...rest}
      style={{ opacity: muted ? 0.55 : 1, ...(rest.style as object) }}
    >
      {initials(name)}
    </Avatar>
  );
}
