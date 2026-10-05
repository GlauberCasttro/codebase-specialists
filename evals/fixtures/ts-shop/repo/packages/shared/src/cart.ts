import type { Sku } from "./sku.ts";

export interface CartLine {
  sku: Sku;
  quantity: number;
  /** Unit price in integer cents, copied from the catalog when the line is added. */
  unitPriceCents: number;
}

export interface Cart {
  id: string;
  customerId: string;
  lines: CartLine[];
}

export function cartSubtotalCents(cart: Cart): number {
  return cart.lines.reduce((sum, line) => sum + line.unitPriceCents * line.quantity, 0);
}
