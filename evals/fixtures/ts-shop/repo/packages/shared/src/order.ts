import type { CartLine } from "./cart.ts";

/**
 * Order lifecycle. A string union, not an enum: packages run under node type stripping.
 * The allowed transitions are enforced by the api (packages/api/src/orders/status.ts).
 */
export type OrderStatus = "pending" | "paid" | "shipped" | "cancelled";

export interface Order {
  id: string;
  cartId: string;
  customerId: string;
  status: OrderStatus;
  lines: CartLine[];
  totalCents: number;
  reservationIds: string[];
}
