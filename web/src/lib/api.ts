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
