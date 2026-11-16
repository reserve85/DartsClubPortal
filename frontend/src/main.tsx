import "@mantine/core/styles.css";
import "@mantine/dates/styles.css";
import "@mantine/notifications/styles.css";
import "@mantine/charts/styles.css";
import "./app.css";

import { createInertiaApp } from "@inertiajs/react";
import { MantineProvider, type MantineColorScheme } from "@mantine/core";
import { DatesProvider } from "@mantine/dates";
import { ModalsProvider } from "@mantine/modals";
import { Notifications } from "@mantine/notifications";
import dayjs from "dayjs";
import "dayjs/locale/de";
import { createRoot } from "react-dom/client";
import AppLayout from "./layout/AppLayout";
import { theme } from "./theme";
import type { SharedProps } from "./types";

const pages = import.meta.glob("./pages/**/*.tsx");

createInertiaApp({
  progress: { color: "#f76707", delay: 150 },
  // Django's CSRF cookie / header names (Inertia defaults to Laravel's).
  http: { xsrfCookieName: "csrftoken", xsrfHeaderName: "X-CSRFToken" },
  title: (title) => title,
  resolve: async (name) => {
    const loader = pages[`./pages/${name}.tsx`];
    if (!loader) throw new Error(`Unknown page: ${name}`);
    const mod = (await loader()) as { default: { layout?: unknown } };
    // Every page uses the app shell unless it sets its own layout (e.g. login).
    if (mod.default.layout === undefined) mod.default.layout = (page: React.ReactNode) => <AppLayout>{page}</AppLayout>;
    return mod.default as never;
  },
  setup({ el, App, props }) {
    const shared = props.initialPage.props as unknown as SharedProps;
    const language = shared.site?.language === "en" ? "en" : "de";
    dayjs.locale(language);
    const pref = (shared.auth?.user?.theme ?? "auto") as MantineColorScheme;
    createRoot(el!).render(
      <MantineProvider theme={theme} defaultColorScheme={pref}>
        <DatesProvider settings={{ locale: language, firstDayOfWeek: 1 }}>
          <ModalsProvider>
            <Notifications position="top-center" zIndex={4000} />
            <App {...props} />
          </ModalsProvider>
        </DatesProvider>
      </MantineProvider>,
    );
  },
});
