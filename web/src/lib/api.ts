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

/** Preço mais recente por cidade, fixando qualidade 1 ("Normal") como
 * referência da comparação. A AODP devolve uma linha por nível de
 * qualidade (1 a 5) na mesma coleta, com o mesmo `collected_at` — sem
 * filtrar por qualidade, o empate de timestamp faria a tabela misturar
 * preço de item raro (qualidade 5) com normal dependendo da cidade, o que
 * não é uma comparação "maçã com maçã". Cai pra qualquer qualidade
 * disponível só se a cidade não tiver nenhum registro de qualidade 1. */
export function latestPricePerCity(rows: PriceRaw[]): Map<string, PriceRaw> {
  const byCity = new Map<string, PriceRaw[]>();
  for (const row of rows) {
    const list = byCity.get(row.city_id);
    if (list) {
      list.push(row);
    } else {
      byCity.set(row.city_id, [row]);
    }
  }

  const latest = new Map<string, PriceRaw>();
  for (const [cityId, cityRows] of byCity) {
    const normalQuality = cityRows.filter((row) => row.quality === 1);
    const pool = normalQuality.length > 0 ? normalQuality : cityRows;
    const mostRecent = pool.reduce((newest, row) =>
      new Date(row.collected_at) > new Date(newest.collected_at) ? row : newest,
    );
    latest.set(cityId, mostRecent);
  }
  return latest;
}
