import { test } from "node:test";
import assert from "node:assert/strict";
import type { Cart, Sku } from "@shop/shared";
import { StockLedger } from "../inventory/stock.ts";
import { ReservationBook } from "../inventory/reservations.ts";
import { cancel, checkout, markPaid } from "./checkout.ts";

const A = "TSH-0001" as Sku;
const B = "MUG-0002" as Sku;

function setup() {
  const stock = new StockLedger();
  stock.setOnHand(A, 5);
  stock.setOnHand(B, 1);
  return { stock, book: new ReservationBook(stock, () => 0) };
}

const cart = (qa: number, qb: number): Cart => ({
  id: "cart_1", customerId: "u1",
  lines: [{ sku: A, quantity: qa, unitPriceCents: 4990 }, { sku: B, quantity: qb, unitPriceCents: 2500 }],
});

test("checkout reserves all lines and totals in cents", () => {
  const { stock, book } = setup();
  const order = checkout(cart(2, 1), book, "ord_1");
  assert.equal(order.status, "pending");
  assert.equal(order.totalCents, 12480);
  assert.equal(stock.available(A), 3);
});

test("checkout is all-or-nothing when one line lacks stock", () => {
  const { stock, book } = setup();
  assert.throws(() => checkout(cart(2, 2), book, "ord_2"));
  assert.equal(stock.available(A), 5);
  assert.equal(stock.available(B), 1);
});

test("quantity per line is limited to 10", () => {
  const { book } = setup();
  assert.throws(() => checkout(cart(11, 1), book, "ord_3"), RangeError);
});

test("shipped orders cannot be cancelled; cancelling a pending order returns stock", () => {
  const { stock, book } = setup();
  const paid = markPaid(checkout(cart(1, 1), book, "ord_4"), book);
  assert.throws(() => cancel({ ...paid, status: "shipped" }, book), /invalid order transition/);
  stock.setOnHand(B, 1);
  const pending = checkout(cart(1, 1), book, "ord_5");
  cancel(pending, book);
  assert.equal(stock.available(B), 1);
});
