import { Affix, Box, Button, Group, Paper, Text, Transition } from "@mantine/core";
import { IconCookie } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { useT } from "../i18n";

const KEY = "dpm_cookie_consent"; // same key as the classic pages

/** Essential-cookies notice, shown once per browser. */
export function CookieNotice() {
  const t = useT();
  const [show, setShow] = useState(false);
  useEffect(() => {
    try {
      setShow(!window.localStorage.getItem(KEY));
    } catch {
      setShow(true); // private mode: no storage -> always show
    }
  }, []);
  const accept = () => {
    try {
      window.localStorage.setItem(KEY, "essential");
    } catch {
      /* ignore */
    }
    setShow(false);
  };
  return (
    <>
    {/* Room below the page while the notice is open, so it never hides a button. */}
    {show && <Box h={{ base: 110, sm: 0 }} aria-hidden />}
    <Affix position={{ bottom: 12, left: 12, right: 12 }} zIndex={300}>
      <Transition transition="slide-up" mounted={show}>
        {(styles) => (
          <Paper style={{ ...styles, maxWidth: 640, margin: "0 auto" }} withBorder shadow="lg" p="md" role="dialog" aria-label={t("Cookie notice")}>
            <Group wrap="nowrap" align="flex-start" gap="sm">
              <IconCookie size={22} style={{ flexShrink: 0 }} />
              <Text size="sm" style={{ flex: 1 }}>{t("This site sets only essential cookies (session for login, your language choice); no tracking or third-party cookies are set.")}</Text>
              <Button size="xs" onClick={accept}>{t("Understood")}</Button>
            </Group>
          </Paper>
        )}
      </Transition>
    </Affix>
    </>
  );
}
