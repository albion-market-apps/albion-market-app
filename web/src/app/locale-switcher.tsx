"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { LOCALE_COOKIE, SUPPORTED_LOCALES } from "@/locale-config";

export function LocaleSwitcher() {
  const locale = useLocale();
  const t = useTranslations("header");
  const router = useRouter();

  function handleChange(next: string) {
    document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=31536000`;
    router.refresh();
  }

  return (
    <label className="flex items-center gap-2 text-sm text-slate-400">
      {t("localeLabel")}
      <select
        value={locale}
        onChange={(event) => handleChange(event.target.value)}
        className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-slate-100"
      >
        {SUPPORTED_LOCALES.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}
