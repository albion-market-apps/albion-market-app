export interface ItemResult {
  id: string;
  code: string;
  name: string;
  tier: number;
  enchant: number;
}

export interface ItemsPage {
  items: ItemResult[];
  page: number;
  page_size: number;
  total: number;
}

export async function fetchItems(query: string): Promise<ItemsPage> {
  const params = query ? `?query=${encodeURIComponent(query)}` : "";
  const response = await fetch(`/api/items${params}`);
  if (!response.ok) {
    throw new Error(`Falha ao buscar itens: ${response.status}`);
  }
  return response.json();
}

export interface City {
  id: string;
  code: string;
  name: string;
}

export async function fetchCities(): Promise<City[]> {
  const response = await fetch("/api/cities");
  if (!response.ok) {
    throw new Error(`Falha ao buscar cidades: ${response.status}`);
  }
  return response.json();
}

export interface PriceRaw {
  id: string;
  item_id: string;
  city_id: string;
  sell_price_min: number;
  sell_price_max: number;
  buy_price_min: number;
  buy_price_max: number;
  quality: number;
  qty: number;
  collected_at: string;
}

export interface PricesResponse {
  item_id: string;
  agg: string;
  data: PriceRaw[];
}

export async function fetchPrices(itemId: string): Promise<PricesResponse> {
  const response = await fetch(`/api/prices?item_id=${encodeURIComponent(itemId)}&agg=raw`);
  if (!response.ok) {
    throw new Error(`Falha ao buscar preços: ${response.status}`);
  }
  return response.json();
}

/** `query_raw_prices` no backend já devolve, por cidade, ordenado por
 * `collected_at DESC` — a primeira linha de cada `city_id` é a mais recente. */
export function latestPricePerCity(rows: PriceRaw[]): Map<string, PriceRaw> {
  const latest = new Map<string, PriceRaw>();
  for (const row of rows) {
    if (!latest.has(row.city_id)) {
      latest.set(row.city_id, row);
    }
  }
  return latest;
}
