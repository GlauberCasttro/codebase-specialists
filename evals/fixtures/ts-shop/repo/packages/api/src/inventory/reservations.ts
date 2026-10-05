import type { Sku } from "@shop/shared";
import type { StockLedger } from "./stock.ts";

/** A reservation holds stock for a cart during checkout; it expires after 15 minutes. */
export const RESERVATION_TTL_MS = 15 * 60 * 1000;

export interface Reservation {
  id: string;
  sku: Sku;
  quantity: number;
  expiresAt: number;
  state: "active" | "confirmed" | "released";
}

export class ReservationBook {
  #stock: StockLedger;
  #now: () => number;
  #items = new Map<string, Reservation>();
  #seq = 0;

  constructor(stock: StockLedger, now: () => number = Date.now) {
    this.#stock = stock;
    this.#now = now;
  }

  reserve(sku: Sku, quantity: number): Reservation {
    this.expireDue();
    this.#stock.take(sku, quantity);
    const reservation: Reservation = {
      id: `rsv_${++this.#seq}`,
      sku,
      quantity,
      expiresAt: this.#now() + RESERVATION_TTL_MS,
      state: "active",
    };
    this.#items.set(reservation.id, reservation);
    return reservation;
  }

  /** @deprecated legacy name used by the mobile app v1 ("hold"); call reserve(). */
  holdStock(sku: Sku, quantity: number): Reservation {
    return this.reserve(sku, quantity);
  }

  confirm(id: string): Reservation {
    const r = this.#get(id);
    if (r.state !== "active" || r.expiresAt <= this.#now()) {
      throw new Error(`reservation ${id} is not active`);
    }
    r.state = "confirmed";
    return r;
  }

  release(id: string): void {
    const r = this.#get(id);
    if (r.state === "active") {
      r.state = "released";
      this.#stock.giveBack(r.sku, r.quantity);
    }
  }

  /** Releases every active reservation past its TTL, returning stock. */
  expireDue(): number {
    let released = 0;
    for (const r of this.#items.values()) {
      if (r.state === "active" && r.expiresAt <= this.#now()) {
        this.release(r.id);
        released++;
      }
    }
    return released;
  }

  #get(id: string): Reservation {
    const r = this.#items.get(id);
    if (!r) throw new Error(`reservation ${id} not found`);
    return r;
  }
}
