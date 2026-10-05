import type { Cart, CartLine, Sku } from "@shop/shared";

/**
 * Client-side cart. Optimistic only: the api re-validates quantity (1..10) and stock at checkout,
 * so the UI clamps to UI_MAX_QTY just for UX. The server rule lives in packages/api/src/orders/rules.ts.
 */
export const UI_MAX_QTY = 10;

export function addLine(cart: Cart, sku: Sku, unitPriceCents: number, quantity = 1): Cart {
  const existing = cart.lines.find((l) => l.sku === sku);
  const lines: CartLine[] = existing
    ? cart.lines.map((l) => (l.sku === sku ? { ...l, quantity: Math.min(UI_MAX_QTY, l.quantity + quantity) } : l))
    : [...cart.lines, { sku, unitPriceCents, quantity: Math.min(UI_MAX_QTY, quantity) }];
  return { ...cart, lines };
}

export function removeLine(cart: Cart, sku: Sku): Cart {
  return { ...cart, lines: cart.lines.filter((l) => l.sku !== sku) };
}

export function lineCount(cart: Cart): number {
  return cart.lines.reduce((n, l) => n + l.quantity, 0);
}
