import type { Sku } from "@shop/shared";

export interface CatalogItem {
  sku: Sku;
  title: string;
  priceCents: number;
  active: boolean;
}

export class Catalog {
  #items = new Map<Sku, CatalogItem>();

  upsert(item: CatalogItem): void {
    if (!Number.isInteger(item.priceCents) || item.priceCents < 0) {
      throw new RangeError("priceCents must be a non-negative integer");
    }
    this.#items.set(item.sku, item);
  }

  get(sku: Sku): CatalogItem | undefined {
    return this.#items.get(sku);
  }

  listActive(): CatalogItem[] {
    return [...this.#items.values()].filter((i) => i.active);
  }
}
