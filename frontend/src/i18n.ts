import { usePage } from "@inertiajs/react";
import type { SharedProps } from "./types";

/**
 * t(msgid, params) -> translated by Django (django.po), e.g. t(<msgid>).
 * Placeholders use Django's %(name)s syntax so the catalog stays one file.
 * After adding a new t(msgid), run `python manage.py sync_frontend_i18n`.
 */
export function useT() {
  const { i18n } = usePage<SharedProps>().props;
  return (msgid: string, params?: Record<string, string | number>) => {
    let text = (i18n && i18n[msgid]) || msgid;
    if (params) {
      for (const [k, v] of Object.entries(params)) text = text.split(`%(${k})s`).join(String(v));
    }
    return text;
  };
}

/** Singular / plural by count: tn("%(n)s match", "%(n)s matches", n). */
export function useTn() {
  const t = useT();
  return (one: string, many: string, n: number) => t(n === 1 ? one : many, { n });
}

export function useFormat() {
  const { site } = usePage<SharedProps>().props;
  const locale = site?.language === "en" ? "en-GB" : "de-DE";
  return {
    number: (v: number | null | undefined, digits = 0) =>
      v === null || v === undefined ? "–" : v.toLocaleString(locale, { minimumFractionDigits: digits, maximumFractionDigits: digits }),
    /** Elo values: whole number, no thousands separator (1785, not 1.785). */
    elo: (v: number | null | undefined) => (v === null || v === undefined ? "–" : String(Math.round(v))),
    signed: (v: number, digits = 1) =>
      `${v > 0 ? "+" : v < 0 ? "−" : "±"}${Math.abs(v).toLocaleString(locale, { minimumFractionDigits: digits, maximumFractionDigits: digits })}`,
    date: (iso: string | null | undefined) => {
      if (!iso) return "–";
      const [y, m, d] = iso.slice(0, 10).split("-");
      return `${d}.${m}.${y}`;
    },
    euro: (v: number | string) => `${Number(v).toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`,
  };
}
