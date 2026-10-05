/** A SKU identifies a sellable variant: three uppercase letters, dash, four digits (e.g. "TSH-0042"). */
export type Sku = string & { readonly __brand: "Sku" };

export const SKU_PATTERN = /^[A-Z]{3}-\d{4}$/;

export function parseSku(raw: string): Sku {
  const value = raw.trim().toUpperCase();
  if (!SKU_PATTERN.test(value)) {
    throw new Error(`invalid SKU "${raw}": expected AAA-0000`);
  }
  return value as Sku;
}
