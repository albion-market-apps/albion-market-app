/** Taxas reais do mercado do jogo (sem Premium — Premium paga metade),
 * confirmadas com print do cliente (turno 16): 8% de taxa de venda (tanto
 * venda instantânea quanto pedido de venda), mais 2,5% de "Taxa de Ordem"
 * só pra pedidos — paga ao criar o pedido, mesmo que ele nunca venda. */
export const SALES_TAX_RATE = 0.08;
export const ORDER_SETUP_FEE_RATE = 0.025;

/** Quanto você recebe vendendo instantaneamente (preenche a melhor ordem
 * de compra já publicada) — só desconta `SALES_TAX_RATE`. */
export function netInstantSellPrice(grossBuyPriceMax: number): number {
  return Math.round(grossBuyPriceMax * (1 - SALES_TAX_RATE));
}

/** Quanto você recebe **se** seu próprio pedido de venda (criado no preço
 * da oferta mais barata já publicada, pra ser competitivo) vender —
 * desconta `SALES_TAX_RATE` + `ORDER_SETUP_FEE_RATE` (essa paga na
 * criação do pedido, perdida mesmo que ele nunca venda). */
export function netSellOrderPrice(grossSellPriceMin: number): number {
  return Math.round(grossSellPriceMin * (1 - SALES_TAX_RATE - ORDER_SETUP_FEE_RATE));
}

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

export interface TradeOpportunity {
  item_id: string;
  item_code: string;
  item_name: string;
  item_tier: number;
  item_enchant: number;
  buy_city_id: string;
  buy_city_name: string;
  buy_price: number;
  sell_city_id: string;
  sell_city_name: string;
  sell_price: number; // venda instantânea, líquida da taxa de 8%
  sell_order_price: number; // pedido de venda, líquido de 8% + 2,5% de taxa de ordem (0 = sem oferta pra basear o preço)
  profit: number;
  collected_at: string;
}

export async function fetchFavoritesOpportunities(
  itemIds: string[],
): Promise<TradeOpportunity[]> {
  if (itemIds.length === 0) return [];
  const response = await fetch(
    `/api/opportunities/favorites?item_ids=${itemIds.map(encodeURIComponent).join(",")}`,
  );
  if (!response.ok) {
    throw new Error(`Falha ao buscar oportunidades dos favoritos: ${response.status}`);
  }
  return response.json();
}

export function itemFromTrade(trade: TradeOpportunity): ItemResult {
  return {
    id: trade.item_id,
    code: trade.item_code,
    name: trade.item_name,
    tier: trade.item_tier,
    enchant: trade.item_enchant,
  };
}

export async function fetchBestFromCity(
  cityId: string,
  limit = 5,
): Promise<TradeOpportunity[]> {
  const response = await fetch(
    `/api/opportunities/best-from-city?city_id=${encodeURIComponent(cityId)}&limit=${limit}`,
  );
  if (!response.ok) {
    throw new Error(`Falha ao buscar melhores oportunidades: ${response.status}`);
  }
  return response.json();
}

/** Top N itens mais lucrativos do catálogo inteiro, sem travar cidade de
 * compra nem de venda — calculado na hora a cada chamada a partir do
 * último preço que o coletor trouxe, não uma lista cacheada de hora em
 * hora (decisão tomada com o usuário: o catálogo é pequeno o bastante pra
 * isso custar bem menos que 1s no backend). */
export async function fetchTopOpportunities(limit = 5): Promise<TradeOpportunity[]> {
  const response = await fetch(`/api/opportunities/top?limit=${limit}`);
  if (!response.ok) {
    throw new Error(`Falha ao buscar top oportunidades: ${response.status}`);
  }
  return response.json();
}

export interface RefiningComparison {
  tier: number;
  raw_item_id: string;
  raw_code: string;
  raw_name: string;
  raw_price: number;
  refined_item_id: string;
  refined_code: string;
  refined_name: string;
  refined_best_price: number;
  refined_best_city_id: string;
  refined_best_city_name: string;
}

/** Preço da matéria-prima na cidade informada ao lado do melhor preço do
 * material refinado — sem calcular lucro, por decisão do usuário (a taxa de
 * retorno real do refino depende de foco/especialização/premium, que a API
 * de preços não sabe). */
export async function fetchRefiningAtCity(cityId: string): Promise<RefiningComparison[]> {
  const response = await fetch(`/api/refining?city_id=${encodeURIComponent(cityId)}`);
  if (!response.ok) {
    throw new Error(`Falha ao buscar dados de refino: ${response.status}`);
  }
  return response.json();
}
