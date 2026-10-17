"use client";

import { useEffect, useState } from "react";
import type { ItemResult } from "@/lib/api";
import { addFavorite, isFavorite, loadFavorites, MAX_FAVORITES, removeFavorite } from "@/lib/favorites";
import { HomeView } from "./home-view";
import { ItemDetailView } from "./item-detail-view";

export default function HomePage() {
  const [selectedItem, setSelectedItem] = useState<ItemResult | null>(null);
  const [favorites, setFavorites] = useState<ItemResult[]>([]);

  // localStorage só existe no browser — carregar depois do mount evita
  // divergência entre o HTML renderizado no servidor e o do cliente.
  useEffect(() => {
    setFavorites(loadFavorites());
  }, []);

  if (selectedItem) {
    return (
      <ItemDetailView
        item={selectedItem}
        isFavorite={isFavorite(favorites, selectedItem.id)}
        canAddFavorite={favorites.length < MAX_FAVORITES}
        onToggleFavorite={() => {
          setFavorites((current) =>
            isFavorite(current, selectedItem.id)
              ? removeFavorite(current, selectedItem.id)
              : addFavorite(current, selectedItem),
          );
        }}
        onBack={() => setSelectedItem(null)}
      />
    );
  }

  return (
    <HomeView
      favorites={favorites}
      onSelectItem={setSelectedItem}
      onRemoveFavorite={(itemId) => setFavorites((current) => removeFavorite(current, itemId))}
    />
  );
}
