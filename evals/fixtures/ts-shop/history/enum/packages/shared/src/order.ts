import type { CartLine } from "./cart.ts";

export enum OrderStatus {
  Pending = "pending",
  Paid = "paid",
  Shipped = "shipped",
  Cancelled = "cancelled",
}

export interface Order {
  id: string;
  cartId: string;
  customerId: string;
  status: OrderStatus;
  lines: CartLine[];
  totalCents: number;
  reservationIds: string[];
}
