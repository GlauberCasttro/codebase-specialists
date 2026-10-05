/** Quantity per cart line must be within 1..MAX_QTY_PER_LINE (ADR 0002). */
export const MAX_QTY_PER_LINE = 10;

export function assertLineQuantity(quantity: number): void {
  if (!Number.isInteger(quantity) || quantity < 1 || quantity > MAX_QTY_PER_LINE) {
    throw new RangeError(`quantity must be an integer in 1..${MAX_QTY_PER_LINE}, got ${quantity}`);
  }
}
