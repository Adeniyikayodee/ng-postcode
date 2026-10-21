import { parse, Postcode } from "ng-postcode-js";
import { ApiError, lookup } from "ng-postcode-js/api";
import { Client, TransportError } from "ng-postcode-js/client";

/**
 * A client for confirming codes, or null without a live key. Test keys answer
 * `not_found` for every code, so they would refuse every order.
 */
export function nipostClient(key = ""): Client | null {
  if (!key.trim()) return null;
  if (/^\s*nipost_(pk_)?test_/.test(key)) {
    console.warn("NG_POSTCODE_API_KEY is a test key, so postcodes are checked offline only.");
    return null;
  }
  // Checkout should not wait long on a third party.
  return new Client(key, { timeoutMs: 3000 });
}

/**
 * Whether NIPOST has assigned the code to a building, or null when it could not say.
 * A level 1 lookup, which uses no credits. Callers should accept the order on null.
 */
export async function isAssigned(postcode: string, client: Client): Promise<boolean | null> {
  const code = parse(postcode);
  if (!(code instanceof Postcode)) return false;
  const found = await client.send(lookup(code, 1));
  if (found instanceof ApiError || found instanceof TransportError) {
    console.warn(`NIPOST lookup failed: ${found}`);
    return null;
  }
  if (found.valid) return true;
  return found.status === "not_found" || found.status === "invalid" ? false : null;
}
