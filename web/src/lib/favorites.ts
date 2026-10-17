import type { ItemResult } from "@/lib/api";

const STORAGE_KEY = "albion:favorites";
export const MAX_FAVORITES = 4;

/** Guarda o item inteiro (não só o id) — assim a seção de favoritos
 * consegue mostrar nome/tier mesmo pro item que ainda não tem preço
 * coletado (a API de oportunidades simplesmente omite esses da resposta,
 * ver backend/app/api/routes/opportunities.py). */
export function loadFavorites(): ItemResult[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function save(favorites: ItemResult[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites));
  } catch {
    // localStorage indisponível (modo privado, bloqueado etc.) — favoritos
    // não persistem, mas a página segue funcionando normalmente.
  }
}

export function isFavorite(favorites: ItemResult[], itemId: string): boolean {
  return favorites.some((item) => item.id === itemId);
}

export function addFavorite(favorites: ItemResult[], item: ItemResult): ItemResult[] {
  if (isFavorite(favorites, item.id) || favorites.length >= MAX_FAVORITES) {
    return favorites;
  }
  const next = [...favorites, item];
  save(next);
  return next;
}

export function removeFavorite(favorites: ItemResult[], itemId: string): ItemResult[] {
  const next = favorites.filter((item) => item.id !== itemId);
  save(next);
  return next;
}
