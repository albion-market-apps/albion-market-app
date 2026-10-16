"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import useSWR from "swr";
import { fetchItems } from "@/lib/api";

export default function HomePage() {
  const t = useTranslations("home");
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");

  const { data: itemsPage, isLoading } = useSWR(
    submittedQuery !== null ? ["items", submittedQuery] : null,
    () => fetchItems(submittedQuery),
  );
  const items = itemsPage?.items;

  return (
    <div className="flex flex-col gap-6 pt-16">
      <h1 className="text-3xl font-semibold">{t("title")}</h1>

      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          setSubmittedQuery(query);
        }}
      >
        <input
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("searchPlaceholder")}
          className="flex-1 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100"
        />
        <button
          type="submit"
          className="rounded bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-500"
        >
          {t("searchButton")}
        </button>
      </form>

      {isLoading && <p className="text-slate-400">...</p>}

      {items && (
        <div>
          <h2 className="mb-2 text-lg font-medium">{t("resultsTitle")}</h2>
          {items.length === 0 ? (
            <p className="text-slate-400">{t("noResults")}</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {items.map((item) => (
                <li
                  key={item.id}
                  className="rounded border border-slate-800 bg-slate-900 px-3 py-2"
                >
                  {item.name} — T{item.tier}
                  {item.enchant > 0 ? `.${item.enchant}` : ""} ({item.code})
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
