import { useState } from "react";
import type { Cart } from "@shop/shared";
import { cartSubtotalCents } from "@shop/shared";
import { postCheckout } from "./api.ts";
import { StockLedger } from "@shop/api/src/inventory/stock.ts";
import { formatPrice } from "./cart/formatPrice.ts";

const localStock = new StockLedger();

export function App() {
  const [cart] = useState<Cart>({ id: "local", customerId: "guest", lines: [] });
  const [status, setStatus] = useState("");
  return (
    <main>
      <h1>Shop</h1>
      <p>Subtotal: {formatPrice(cartSubtotalCents(cart))}</p>
      <button onClick={() => postCheckout(cart).then((o) => setStatus(o.status), (e: Error) => setStatus(e.message))}>
        Finalizar compra
      </button>
      <p role="status">{status}</p>
      <small>em estoque: {cart.lines.map((l) => localStock.available(l.sku)).join(", ")}</small>
    </main>
  );
}
