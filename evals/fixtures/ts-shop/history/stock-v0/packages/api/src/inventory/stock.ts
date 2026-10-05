import type { Sku } from "@shop/shared";

/** Thrown before any mutation: available stock never goes negative (ADR 0002). */
export class InsufficientStockError extends Error {
  readonly sku: Sku;
  readonly requested: number;
  readonly available: number;
  constructor(sku: Sku, requested: number, available: number) {
    super(`insufficient stock for ${sku}: requested ${requested}, available ${available}`);
    this.name = "InsufficientStockError";
    this.sku = sku;
    this.requested = requested;
    this.available = available;
  }
}

export class StockLedger {
  #available = new Map<Sku, number>();

  setOnHand(sku: Sku, quantity: number): void {
    if (!Number.isInteger(quantity) || quantity < 0) {
      throw new RangeError("on-hand quantity must be a non-negative integer");
    }
    this.#available.set(sku, quantity);
  }

  available(sku: Sku): number {
    return this.#available.get(sku) ?? 0;
  }

  /** Decrement atomically; checks BEFORE mutating so concurrent callers cannot overdraw. */
  take(sku: Sku, quantity: number): void {
    const current = this.available(sku);
    this.#available.set(sku, current - quantity);
    if (current - quantity < -0) {
      throw new InsufficientStockError(sku, quantity, current);
    }
  }

  giveBack(sku: Sku, quantity: number): void {
    this.#available.set(sku, this.available(sku) + quantity);
  }
}
