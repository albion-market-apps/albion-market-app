"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import useSWR from "swr";
import {
  fetchCities,
  fetchPrices,
  latestPricePerCity,
  netInstantSellPrice,
  netSellOrderPrice,
  type City,
  type ItemResult,
  type PriceRaw,
} from "@/lib/api";
import { MAX_FAVORITES } from "@/lib/favorites";

type CityPriceRow = { city: City; price: PriceRaw };

/** Melhor par (cidade de compra, cidade de venda) maximizando o lucro **já
 * líquido de taxa** (venda instantânea) — sempre cidades diferentes.
 * Comprar e "vender" na mesma cidade não é arbitragem nenhuma (sem
 * viagem, não tem razão pra tratar compra e venda como lugares
 * separados). Busca exaustiva sobre os pares — no máximo 7 cidades, O(n²)
 * é barato. Mesmo algoritmo usado no backend
 * (`app/services/opportunities.py::best_trade_for_item`), pra calculadora
 * e API nunca se contradizerem. */
function findBestTrade(
  rows: CityPriceRow[],
): { buy: CityPriceRow; sell: CityPriceRow; profit: number } | null {
  let best: { buy: CityPriceRow; sell: CityPriceRow; profit: number } | null = null;
  for (const buy of rows) {
    for (const sell of rows) {
      if (buy.city.id === sell.city.id) continue;
      const profit = netInstantSellPrice(sell.price.buy_price_max) - buy.price.sell_price_min;
      if (!best || profit > best.profit) {
        best = { buy, sell, profit };
      }
    }
  }
  return best;
}

export function ItemDetailView({
  item,
  isFavorite,
  canAddFavorite,
  onToggleFavorite,
  onBack,
}: {
  item: ItemResult;
  isFavorite: boolean;
  canAddFavorite: boolean;
  onToggleFavorite: () => void;
  onBack: () => void;
}) {
  const t = useTranslations("home");
  const { data: cities } = useSWR("cities", fetchCities);
  const { data: pricesResponse, isLoading } = useSWR(["prices", item.id], () =>
    fetchPrices(item.id),
  );

  const latestByCity = pricesResponse ? latestPricePerCity(pricesResponse.data) : new Map();
  const rows = (cities ?? [])
    .map((city) => ({ city, price: latestByCity.get(city.id) ?? null }))
    .filter((row): row is { city: City; price: PriceRaw } => row.price !== null)
    .sort((a, b) => a.price.sell_price_min - b.price.sell_price_min);

  const bestTrade = findBestTrade(rows);
  const cheapestToBuy = bestTrade?.buy ?? null;
  const bestToSell = bestTrade?.sell ?? null;

  const favoriteDisabled = !isFavorite && !canAddFavorite;

  return (
    <div className="flex flex-col gap-6 pt-16">
      <div className="flex items-center justify-between gap-3">
        <button onClick={onBack} className="text-sm text-emerald-400 hover:underline">
          ← {t("backToSearch")}
        </button>
        <button
          onClick={onToggleFavorite}
          disabled={favoriteDisabled}
          title={favoriteDisabled ? t("favoritesFull", { max: MAX_FAVORITES }) : undefined}
          className="text-sm text-amber-400 hover:underline disabled:cursor-not-allowed disabled:text-slate-600 disabled:no-underline"
        >
          {isFavorite ? t("removeFavorite") : t("addFavorite")}
        </button>
      </div>

      <div>
        <h1 className="text-2xl font-semibold">{t("comparisonTitle")}</h1>
        <p className="text-slate-400">
          {item.name} — T{item.tier}
          {item.enchant > 0 ? `.${item.enchant}` : ""}
        </p>
      </div>

      {isLoading && <p className="text-slate-400">...</p>}

      {!isLoading && rows.length === 0 && <p className="text-slate-400">{t("noPriceData")}</p>}

      {rows.length > 0 && (
        <>
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
                    {price.sell_price_min.toLocaleString()}
                    {city.id === cheapestToBuy?.city.id && (
                      <span className="ml-2 rounded bg-emerald-900 px-2 py-0.5 text-xs text-emerald-300">
                        {t("bestToBuy")}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {price.buy_price_max.toLocaleString()}
                    {city.id === bestToSell?.city.id && (
                      <span className="ml-2 rounded bg-amber-900 px-2 py-0.5 text-xs text-amber-300">
                        {t("bestToSell")}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-sm text-slate-400">
                    {new Date(price.collected_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-slate-500">{t("pricesAreGross")}</p>

          {cheapestToBuy && bestToSell && (
            <InvestmentCalculator
              buyCity={cheapestToBuy.city.name}
              buyPrice={cheapestToBuy.price.sell_price_min}
              sellCity={bestToSell.city.name}
              sellInstantPrice={netInstantSellPrice(bestToSell.price.buy_price_max)}
              sellOrderPrice={
                bestToSell.price.sell_price_min > 0
                  ? netSellOrderPrice(bestToSell.price.sell_price_min)
                  : null
              }
            />
          )}
        </>
      )}
    </div>
  );
}

function InvestmentCalculator({
  buyCity,
  buyPrice,
  sellCity,
  sellInstantPrice,
  sellOrderPrice,
}: {
  buyCity: string;
  buyPrice: number;
  sellCity: string;
  sellInstantPrice: number;
  sellOrderPrice: number | null;
}) {
  const t = useTranslations("home");
  const [investment, setInvestment] = useState("");
  const amount = Number(investment) || 0;
  const units = buyPrice > 0 ? Math.floor(amount / buyPrice) : 0;
  const cost = units * buyPrice;

  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-4">
      <h2 className="mb-1 text-lg font-medium">{t("calculatorTitle")}</h2>
      <p className="mb-3 text-sm text-slate-400">
        {t("buyAtLabel", { city: buyCity, price: buyPrice.toLocaleString() })}
      </p>

      <label className="flex flex-col gap-1 text-sm text-slate-400">
        {t("calculatorInvestment")}
        <input
          type="number"
          min="0"
          inputMode="numeric"
          value={investment}
          onChange={(event) => setInvestment(event.target.value)}
          className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
        />
      </label>

      {amount > 0 && units === 0 && (
        <p className="mt-3 text-slate-400">{t("calculatorNotEnough")}</p>
      )}

      {units > 0 && (
        <div className="mt-3 flex flex-col gap-4 text-sm">
          <p className="text-slate-300">{t("calculatorUnits", { units })}</p>
          <p className="text-slate-400">
            {t("calculatorCost")}: {cost.toLocaleString()}
          </p>

          <SellScenario
            label={t("sellInstantScenario")}
            description={t("sellAtLabel", {
              city: sellCity,
              price: sellInstantPrice.toLocaleString(),
            })}
            revenue={units * sellInstantPrice}
            cost={cost}
          />

          {sellOrderPrice !== null ? (
            <SellScenario
              label={t("sellOrderScenario")}
              description={t("sellAtLabel", {
                city: sellCity,
                price: sellOrderPrice.toLocaleString(),
              })}
              revenue={units * sellOrderPrice}
              cost={cost}
              note={t("sellOrderNote")}
            />
          ) : (
            <p className="text-slate-500">{t("sellOrderNoData")}</p>
          )}
        </div>
      )}
    </div>
  );
}

function SellScenario({
  label,
  description,
  revenue,
  cost,
  note,
}: {
  label: string;
  description: string;
  revenue: number;
  cost: number;
  note?: string;
}) {
  const t = useTranslations("home");
  const profit = revenue - cost;
  return (
    <div className="rounded border border-slate-800 bg-slate-950 p-3">
      <p className="font-medium text-slate-200">{label}</p>
      <p className="text-slate-400">{description}</p>
      <p className="text-slate-400">
        {t("calculatorRevenue")}: {revenue.toLocaleString()}
      </p>
      <p className={profit >= 0 ? "font-medium text-emerald-400" : "font-medium text-red-400"}>
        {t("calculatorProfit")}: {profit.toLocaleString()}
      </p>
      {note && <p className="mt-1 text-xs text-slate-500">{note}</p>}
    </div>
  );
}
