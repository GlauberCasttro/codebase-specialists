import { test } from "node:test";
import assert from "node:assert/strict";
import { parseSku } from "./sku.ts";
import { cartSubtotalCents } from "./cart.ts";

test("parseSku normalizes case and validates AAA-0000", () => {
  assert.equal(parseSku(" tsh-0042 "), "TSH-0042");
  assert.throws(() => parseSku("TSH42"), /invalid SKU/);
});

test("cart subtotal is integer cents", () => {
  const cart = {
    id: "c1", customerId: "u1",
    lines: [{ sku: parseSku("TSH-0042"), quantity: 3, unitPriceCents: 1999 }],
  };
  assert.equal(cartSubtotalCents(cart), 5997);
});
