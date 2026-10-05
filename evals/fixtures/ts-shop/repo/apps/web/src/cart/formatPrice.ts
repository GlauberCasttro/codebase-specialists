/** Formats integer cents as BRL for display only. Never parse the result back into a price. */
export function formatPrice(cents: number): string {
  if (!Number.isInteger(cents)) throw new TypeError("price must be integer cents");
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const reais = Math.floor(abs / 100).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${sign}R$ ${reais},${String(abs % 100).padStart(2, "0")}`;
}
