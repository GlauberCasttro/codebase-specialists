import { Router } from "express";
import { z } from "zod";
import { parseSku } from "@shop/shared";
import type { Catalog } from "../catalog/catalog.ts";
import type { ReservationBook } from "../inventory/reservations.ts";
import { checkout } from "../orders/checkout.ts";
import { MAX_QTY_PER_LINE } from "../orders/rules.ts";

const CheckoutBody = z.object({
  cartId: z.string().min(1),
  customerId: z.string().min(1),
  lines: z.array(z.object({
    sku: z.string().transform(parseSku),
    quantity: z.number().int().min(1).max(MAX_QTY_PER_LINE),
  })).min(1),
});

export function buildRouter(catalog: Catalog, book: ReservationBook): Router {
  const router = Router();

  router.get("/catalog", (_req, res) => {
    res.json(catalog.listActive());
  });

  router.post("/checkout", (req, res) => {
    const parsed = CheckoutBody.safeParse(req.body);
    if (!parsed.success) return res.status(400).json({ error: parsed.error.flatten() });
    const lines = parsed.data.lines.map((l) => {
      const item = catalog.get(l.sku);
      if (!item || !item.active) throw new Error(`unknown sku ${l.sku}`);
      return { sku: l.sku, quantity: l.quantity, unitPriceCents: item.priceCents };
    });
    const order = checkout({ id: parsed.data.cartId, customerId: parsed.data.customerId, lines },
      book, `ord_${Date.now()}`);
    return res.status(201).json(order);
  });

  return router;
}
