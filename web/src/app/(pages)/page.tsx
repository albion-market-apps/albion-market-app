"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import useSWR from "swr";
import {
  fetchCities,
  fetchItems,
  fetchPrices,
  latestPricePerCity,
  type ItemResult,
} from "@/lib/api";

export default function HomePage() {
  const t = useTranslations("home");
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [selectedItem, setSelectedItem] = useState<ItemResult | null>(null);

  const { data: itemsPage, isLoading: isLoadingItems } = useSWR(
    !selectedItem && submittedQuery !== null ? ["items", submittedQuery] : null,
    () => fetchItems(submittedQuery),
  );
  const items = itemsPage?.items;

  const { data: cities } = useSWR("cities", fetchCities);
  const { data: pricesResponse, isLoading: isLoadingPrices } = useSWR(
    selectedItem ? ["prices", selectedItem.id] : null,
    () => fetchPrices(selectedItem!.id),
  );

  if (selectedItem) {
    const latestByCity = pricesResponse ? latestPricePerCity(pricesResponse.data) : new Map();
    const rows = (cities ?? [])
      .map((city) => ({ city, price: latestByCity.get(city.id) ?? null }))
      .filter((row) => row.price !== null)
      .sort((a, b) => a.price!.sell_price_min - b.price!.sell_price_min);

    const cheapestToBuyId = rows[0]?.city.id;
    const bestToSellId = [...rows].sort(
      (a, b) => b.price!.buy_price_max - a.price!.buy_price_max,
    )[0]?.city.id;

    return (
      <div className="flex flex-col gap-6 pt-16">
        <button
          onClick={() => setSelectedItem(null)}
          className="self-start text-sm text-emerald-400 hover:underline"
        >
          ← {t("backToSearch")}
        </button>

        <div>
          <h1 className="text-2xl font-semibold">{t("comparisonTitle")}</h1>
          <p className="text-slate-400">
            {selectedItem.name} — T{selectedItem.tier}
            {selectedItem.enchant > 0 ? `.${selectedItem.enchant}` : ""}
          </p>
        </div>

        {isLoadingPrices && <p className="text-slate-400">...</p>}

        {!isLoadingPrices && rows.length === 0 && (
          <p className="text-slate-400">{t("noPriceData")}</p>
        )}

        {rows.length > 0 && (
          <table className="w-full border-collapse overflow-hidden rounded border border-slate-800 text-left">
            <thead className="bg-slate-900 text-sm text-slate-400">
              <tr>
                <th className="px-3 py-2">{t("cityColumn")}</th>
                <th className="px-3 py-2">{t("sellColumn")}</th>
                <th className="px-3 py-2">{t("buyColumn")}</th>
                <th className="px-3 py-2">{t("updatedColumn")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ city, price }) => (
                <tr key={city.id} className="border-t border-slate-800">
                  <td className="px-3 py-2 font-medium">{city.name}</td>
                  <td className="px-3 py-2">
                    {price!.sell_price_min.toLocaleString()}
                    {city.id === cheapestToBuyId && (
                      <span className="ml-2 rounded bg-emerald-900 px-2 py-0.5 text-xs text-emerald-300">
                        {t("bestToBuy")}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {price!.buy_price_max.toLocaleString()}
                    {city.id === bestToSellId && (
                      <span className="ml-2 rounded bg-amber-900 px-2 py-0.5 text-xs text-amber-300">
                        {t("bestToSell")}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-sm text-slate-400">
                    {new Date(price!.collected_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    );
  }

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

      {isLoadingItems && <p className="text-slate-400">...</p>}

      {items && (
        <div>
          <h2 className="mb-2 text-lg font-medium">{t("resultsTitle")}</h2>
          {items.length === 0 ? (
            <p className="text-slate-400">{t("noResults")}</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {items.map((item) => (
                <li key={item.id}>
                  <button
                    onClick={() => setSelectedItem(item)}
                    className="w-full rounded border border-slate-800 bg-slate-900 px-3 py-2 text-left hover:border-emerald-600"
                  >
                    {item.name} — T{item.tier}
                    {item.enchant > 0 ? `.${item.enchant}` : ""} ({item.code})
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
