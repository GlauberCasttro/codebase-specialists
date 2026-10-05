import type { OrderStatus } from "@shop/shared";

/** pending -> paid -> shipped; pending|paid -> cancelled. shipped and cancelled are terminal. */
export const ORDER_TRANSITIONS: Readonly<Record<OrderStatus, readonly OrderStatus[]>> = {
  pending: ["paid", "cancelled"],
  paid: ["shipped", "cancelled"],
  shipped: [],
  cancelled: [],
};

export function assertTransition(from: OrderStatus, to: OrderStatus): void {
  if (!ORDER_TRANSITIONS[from].includes(to)) {
    throw new Error(`invalid order transition ${from} -> ${to}`);
  }
}
