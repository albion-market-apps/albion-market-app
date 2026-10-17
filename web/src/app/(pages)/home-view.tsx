"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import useSWR from "swr";
import {
  fetchBestFromCity,
  fetchCities,
  fetchFavoritesOpportunities,
  fetchItems,
  fetchRefiningAtCity,
  fetchTopOpportunities,
  itemFromTrade,
  type ItemResult,
  type RefiningComparison,
  type TradeOpportunity,
} from "@/lib/api";

const AUTOCOMPLETE_DEBOUNCE_MS = 300;

function useDebouncedValue(value: string, delayMs: number): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

export function HomeView({
  favorites,
  onSelectItem,
  onRemoveFavorite,
}: {
  favorites: ItemResult[];
  onSelectItem: (item: ItemResult) => void;
  onRemoveFavorite: (itemId: string) => void;
}) {
  const t = useTranslations("home");
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query, AUTOCOMPLETE_DEBOUNCE_MS);

  const { data: itemsPage } = useSWR(
    debouncedQuery.trim() !== "" ? ["items-autocomplete", debouncedQuery] : null,
    () => fetchItems(debouncedQuery),
  );
  const suggestions = itemsPage?.items ?? [];

  const favoriteIds = favorites.map((item) => item.id);
  const { data: favoritesOpportunities } = useSWR(
    favoriteIds.length > 0 ? ["favorites-opportunities", favoriteIds.join(",")] : null,
    () => fetchFavoritesOpportunities(favoriteIds),
  );
  const opportunityByItemId = new Map(
    (favoritesOpportunities ?? []).map((trade) => [trade.item_id, trade]),
  );

  const {
    data: topOpportunities,
    isLoading: isLoadingTop,
    isValidating: isRefreshingTop,
    mutate: refreshTop,
  } = useSWR("top-opportunities", () => fetchTopOpportunities(5));

  const { data: cities } = useSWR("cities", fetchCities);
  const [selectedCityId, setSelectedCityId] = useState("");
  const [queriedCityId, setQueriedCityId] = useState<string | null>(null);
  const { data: bestOpportunities, isLoading: isLoadingBest } = useSWR(
    queriedCityId ? ["best-from-city", queriedCityId] : null,
    () => fetchBestFromCity(queriedCityId!),
  );
  const { data: refiningRows, isLoading: isLoadingRefining } = useSWR(
    queriedCityId ? ["refining-at-city", queriedCityId] : null,
    () => fetchRefiningAtCity(queriedCityId!),
  );

  return (
    <div className="flex flex-col gap-10 pt-16">
      <div className="flex flex-col gap-3">
        <h1 className="text-3xl font-semibold">{t("title")}</h1>

        <div className="relative">
          <input
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("searchPlaceholder")}
            className="w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100"
          />
          {suggestions.length > 0 && (
            <ul className="absolute z-10 mt-1 flex w-full flex-col overflow-hidden rounded border border-slate-700 bg-slate-900 shadow-lg">
              {suggestions.map((item) => (
                <li key={item.id}>
                  <button
                    onClick={() => {
                      setQuery("");
                      onSelectItem(item);
                    }}
                    className="w-full px-3 py-2 text-left hover:bg-slate-800"
                  >
                    {item.name} — T{item.tier}
                    {item.enchant > 0 ? `.${item.enchant}` : ""} ({item.code})
                  </button>
                </li>
              ))}
            </ul>
          )}
          {debouncedQuery.trim() !== "" && suggestions.length === 0 && (
            <p className="mt-1 text-sm text-slate-400">{t("noResults")}</p>
          )}
        </div>
      </div>

      <section className="flex flex-col gap-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-medium">{t("topOpportunitiesTitle")}</h2>
            <p className="text-sm text-slate-400">{t("topOpportunitiesSubtitle")}</p>
          </div>
          <button
            onClick={() => refreshTop()}
            disabled={isRefreshingTop}
            className="shrink-0 rounded border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:border-emerald-600 hover:text-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("refreshButton")}
          </button>
        </div>

        {isLoadingTop && <p className="text-slate-400">...</p>}

        {topOpportunities && (
          <OpportunityList
            opportunities={topOpportunities}
            emptyMessage={t("topOpportunitiesEmpty")}
            numbered
            onSelectItem={(itemId) => {
              const trade = topOpportunities.find((o) => o.item_id === itemId);
              if (trade) onSelectItem(itemFromTrade(trade));
            }}
          />
        )}
      </section>

      <section className="flex flex-col gap-3">
        <div>
          <h2 className="text-lg font-medium">{t("whereAmITitle")}</h2>
          <p className="text-sm text-slate-400">{t("whereAmISubtitle")}</p>
        </div>
        <div className="flex gap-2">
          <select
            value={selectedCityId}
            onChange={(event) => setSelectedCityId(event.target.value)}
            className="flex-1 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100"
          >
            <option value="">{t("citySelectPlaceholder")}</option>
            {(cities ?? []).map((city) => (
              <option key={city.id} value={city.id}>
                {city.name}
              </option>
            ))}
          </select>
          <button
            disabled={!selectedCityId}
            onClick={() => setQueriedCityId(selectedCityId)}
            className="rounded bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("whereAmIButton")}
          </button>
        </div>

        {isLoadingBest && <p className="text-slate-400">...</p>}

        {bestOpportunities && (
          <OpportunityList
            opportunities={bestOpportunities}
            emptyMessage={t("whereAmIEmpty")}
            numbered
            onSelectItem={(itemId) => {
              const trade = bestOpportunities.find((o) => o.item_id === itemId);
              if (trade) onSelectItem(itemFromTrade(trade));
            }}
          />
        )}

        {queriedCityId && (
          <>
            <h3 className="mt-2 text-sm font-medium text-slate-400">{t("refiningTitle")}</h3>
            <p className="text-sm text-slate-500">{t("refiningSubtitle")}</p>
          </>
        )}

        {isLoadingRefining && <p className="text-slate-400">...</p>}

        {refiningRows && (
          <RefiningTable
            rows={refiningRows}
            emptyMessage={t("refiningEmpty")}
            onSelectItem={onSelectItem}
          />
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-medium">{t("favoritesTitle")}</h2>
        {favorites.length === 0 ? (
          <p className="text-slate-400">{t("favoritesEmpty")}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {favorites.map((item) => {
              const trade = opportunityByItemId.get(item.id);
              return (
                <li
                  key={item.id}
                  className="flex items-center justify-between gap-3 rounded border border-slate-800 bg-slate-900 px-3 py-2"
                >
                  <button onClick={() => onSelectItem(item)} className="flex-1 text-left">
                    <div className="font-medium">
                      {item.name} — T{item.tier}
                      {item.enchant > 0 ? `.${item.enchant}` : ""}
                    </div>
                    {trade ? (
                      <div className="text-sm text-slate-400">
                        {t("buyAtLabel", {
                          city: trade.buy_city_name,
                          price: trade.buy_price.toLocaleString(),
                        })}{" "}
                        ·{" "}
                        {t("sellAtLabel", {
                          city: trade.sell_city_name,
                          price: trade.sell_price.toLocaleString(),
                        })}{" "}
                        · {t("profitLabel")}: {trade.profit.toLocaleString()}
                        {trade.sell_order_price > 0 && (
                          <>
                            {" "}
                            ·{" "}
                            {t("sellOrderHint", {
                              price: trade.sell_order_price.toLocaleString(),
                            })}
                          </>
                        )}
                      </div>
                    ) : (
                      <div className="text-sm text-slate-500">{t("favoriteNoData")}</div>
                    )}
                  </button>
                  <button
                    onClick={() => onRemoveFavorite(item.id)}
                    className="text-sm text-slate-400 hover:text-red-400"
                    aria-label={t("removeFavorite")}
                  >
                    ✕
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}

function RefiningTable({
  rows,
  emptyMessage,
  onSelectItem,
}: {
  rows: RefiningComparison[];
  emptyMessage: string;
  onSelectItem: (item: ItemResult) => void;
}) {
  const t = useTranslations("home");

  if (rows.length === 0) {
    return <p className="text-slate-400">{emptyMessage}</p>;
  }

  return (
    <table className="w-full border-collapse overflow-hidden rounded border border-slate-800 text-left">
      <thead className="bg-slate-900 text-sm text-slate-400">
        <tr>
          <th className="px-3 py-2">{t("refiningTierColumn")}</th>
          <th className="px-3 py-2">{t("refiningRawColumn")}</th>
          <th className="px-3 py-2">{t("refiningRefinedColumn")}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={`${row.raw_item_id}-${row.refined_item_id}`} className="border-t border-slate-800">
            <td className="px-3 py-2 text-slate-400">T{row.tier}</td>
            <td className="px-3 py-2">
              <button
                onClick={() =>
                  onSelectItem({
                    id: row.raw_item_id,
                    code: row.raw_code,
                    name: row.raw_name,
                    tier: row.tier,
                    enchant: 0,
                  })
                }
                className="text-left hover:text-emerald-400"
              >
                {row.raw_name} — {row.raw_price.toLocaleString()}
              </button>
            </td>
            <td className="px-3 py-2">
              <button
                onClick={() =>
                  onSelectItem({
                    id: row.refined_item_id,
                    code: row.refined_code,
                    name: row.refined_name,
                    tier: row.tier,
                    enchant: 0,
                  })
                }
                className="text-left hover:text-emerald-400"
              >
                {row.refined_name} — {row.refined_best_price.toLocaleString()} (
                {row.refined_best_city_name})
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function OpportunityList({
  opportunities,
  emptyMessage,
  onSelectItem,
  numbered = false,
}: {
  opportunities: TradeOpportunity[];
  emptyMessage: string;
  onSelectItem: (itemId: string) => void;
  numbered?: boolean;
}) {
  const t = useTranslations("home");

  if (opportunities.length === 0) {
    return <p className="text-slate-400">{emptyMessage}</p>;
  }
  return (
    <ul className="flex flex-col gap-2">
      {opportunities.map((trade, index) => (
        <li key={trade.item_id} className="flex items-start gap-3">
          {numbered && (
            <span className="pt-2 text-sm font-medium text-slate-500">{index + 1}.</span>
          )}
          <button
            onClick={() => onSelectItem(trade.item_id)}
            className="flex-1 rounded border border-slate-800 bg-slate-900 px-3 py-2 text-left hover:border-emerald-600"
          >
            <div className="font-medium">{trade.item_name}</div>
            <div className="text-sm text-slate-400">
              {t("buyAtLabel", { city: trade.buy_city_name, price: trade.buy_price.toLocaleString() })}
              {" · "}
              {t("sellAtLabel", { city: trade.sell_city_name, price: trade.sell_price.toLocaleString() })}
              {" · "}
              {t("profitLabel")}: {trade.profit.toLocaleString()}
              {trade.sell_order_price > 0 && (
                <>
                  {" · "}
                  {t("sellOrderHint", { price: trade.sell_order_price.toLocaleString() })}
                </>
              )}
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}
