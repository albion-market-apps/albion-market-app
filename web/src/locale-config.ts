export const SUPPORTED_LOCALES = ["pt-BR", "en-US"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "pt-BR";
export const LOCALE_COOKIE = "locale";

export function resolveLocale(raw: string | undefined): Locale {
  return (SUPPORTED_LOCALES as readonly string[]).includes(raw ?? "")
    ? (raw as Locale)
    : DEFAULT_LOCALE;
}
