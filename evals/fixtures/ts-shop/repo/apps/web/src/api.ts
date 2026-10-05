import type { Cart, Order } from "@shop/shared";

/** The only way the web talks to the api: HTTP (ADR 0001). */
export async function postCheckout(cart: Cart): Promise<Order> {
  const res = await fetch("/api/checkout", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      cartId: cart.id, customerId: cart.customerId,
      lines: cart.lines.map((l) => ({ sku: l.sku, quantity: l.quantity })),
    }),
  });
  if (!res.ok) throw new Error(`checkout failed: ${res.status}`);
  return (await res.json()) as Order;
}
