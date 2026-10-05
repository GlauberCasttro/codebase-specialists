import { test } from "node:test";
import assert from "node:assert/strict";
import type { Sku } from "@shop/shared";
import { InsufficientStockError, StockLedger } from "./stock.ts";
import { RESERVATION_TTL_MS, ReservationBook } from "./reservations.ts";

const SKU = "TSH-0042" as Sku;

test("stock never goes negative: take fails before mutating", () => {
  const stock = new StockLedger();
  stock.setOnHand(SKU, 2);
  assert.throws(() => stock.take(SKU, 3), InsufficientStockError);
  assert.equal(stock.available(SKU), 2);
});

test("two reservations cannot overdraw the same SKU", () => {
  const stock = new StockLedger();
  stock.setOnHand(SKU, 3);
  const book = new ReservationBook(stock, () => 0);
  book.reserve(SKU, 2);
  assert.throws(() => book.reserve(SKU, 2), InsufficientStockError);
  assert.equal(stock.available(SKU), 1);
});

test("reservation expires after 15 minutes and returns stock", () => {
  let now = 1_000;
  const stock = new StockLedger();
  stock.setOnHand(SKU, 5);
  const book = new ReservationBook(stock, () => now);
  const r = book.reserve(SKU, 5);
  assert.equal(RESERVATION_TTL_MS, 900_000);
  now += RESERVATION_TTL_MS;
  assert.equal(book.expireDue(), 1);
  assert.equal(stock.available(SKU), 5);
  assert.throws(() => book.confirm(r.id), /not active/);
});
