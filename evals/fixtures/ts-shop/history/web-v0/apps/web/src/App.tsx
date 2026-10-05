import { useState } from "react";
import type { Cart } from "@shop/shared";
import { cartSubtotalCents } from "@shop/shared";
import { formatPrice } from "./cart/formatPrice.ts";

export function App() {
  const [cart] = useState<Cart>({ id: "local", customerId: "guest", lines: [] });
  return (
    <main>
      <h1>Shop</h1>
      <p>Subtotal: {formatPrice(cartSubtotalCents(cart))}</p>
    </main>
  );
}
