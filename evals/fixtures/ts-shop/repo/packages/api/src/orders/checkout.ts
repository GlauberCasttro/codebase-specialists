import type { Cart, Order } from "@shop/shared";
import type { ReservationBook } from "../inventory/reservations.ts";
import { assertLineQuantity } from "./rules.ts";
import { assertTransition } from "./status.ts";

/**
 * Turns a cart into a pending order. Stock is only RESERVED here; it is confirmed on payment.
 * If any line cannot be reserved, every reservation made so far is released (all or nothing).
 */
export function checkout(cart: Cart, book: ReservationBook, orderId: string): Order {
  if (cart.lines.length === 0) throw new Error("cannot checkout an empty cart");
  cart.lines.forEach((line) => assertLineQuantity(line.quantity));
  const reservationIds: string[] = [];
  try {
    for (const line of cart.lines) {
      reservationIds.push(book.reserve(line.sku, line.quantity).id);
    }
  } catch (err) {
    reservationIds.forEach((id) => book.release(id));
    throw err;
  }
  const totalCents = cart.lines.reduce((s, l) => s + l.unitPriceCents * l.quantity, 0);
  return {
    id: orderId, cartId: cart.id, customerId: cart.customerId, status: "pending",
    lines: cart.lines, totalCents, reservationIds,
  };
}

export function markPaid(order: Order, book: ReservationBook): Order {
  assertTransition(order.status, "paid");
  order.reservationIds.forEach((id) => book.confirm(id));
  return { ...order, status: "paid" };
}

export function cancel(order: Order, book: ReservationBook): Order {
  assertTransition(order.status, "cancelled");
  order.reservationIds.forEach((id) => book.release(id));
  return { ...order, status: "cancelled" };
}
