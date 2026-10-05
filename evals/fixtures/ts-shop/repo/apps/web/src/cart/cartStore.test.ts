import { test } from "node:test";
import assert from "node:assert/strict";
import type { Cart, Sku } from "@shop/shared";
import { addLine, lineCount, removeLine, UI_MAX_QTY } from "./cartStore.ts";
import { formatPrice } from "./formatPrice.ts";

const empty: Cart = { id: "c1", customerId: "u1", lines: [] };
const SKU = "TSH-0042" as Sku;

test("adding the same SKU merges lines and clamps to the UI max", () => {
  let cart = addLine(empty, SKU, 4990, 7);
  cart = addLine(cart, SKU, 4990, 7);
  assert.equal(cart.lines.length, 1);
  assert.equal(cart.lines[0]?.quantity, UI_MAX_QTY);
  assert.equal(lineCount(removeLine(cart, SKU)), 0);
});

test("formatPrice renders integer cents as BRL", () => {
  assert.equal(formatPrice(123456), "R$ 1.234,56");
  assert.throws(() => formatPrice(12.5), TypeError);
});
