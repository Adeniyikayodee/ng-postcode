/** HTTP shell over `api`, built on `fetch`: the only module that performs I/O. */

import { type ApiError, BASE_URL, decode, type Request } from "./api.js";

export const TIMEOUT_MS = 10_000;

/** The request never produced a response: DNS, TLS, timeout and the like. */
export class TransportError {
  constructor(readonly reason: string) {}

  toString(): string {
    return this.reason;
  }
}

export interface ClientOptions {
  /** Another host, such as a staging stack or a mock. */
  readonly baseUrl?: string;
  /** Your own `fetch`, for proxies or tests. */
  readonly fetch?: typeof fetch;
  readonly timeoutMs?: number;
}

export class Client {
  readonly #apiKey: string;
  readonly #baseUrl: string;
  readonly #fetch: typeof fetch;
  readonly #timeoutMs: number;

  constructor(apiKey: string, options: ClientOptions = {}) {
    // Surrounding whitespace, as read from a file, is dropped.
    this.#apiKey = apiKey.trim();
    this.#baseUrl = options.baseUrl ?? BASE_URL;
    this.#fetch = options.fetch ?? globalThis.fetch;
    this.#timeoutMs = options.timeoutMs ?? TIMEOUT_MS;
  }

  async send<T>(request: Request<T>): Promise<T | ApiError | TransportError> {
    // A key no header can hold is refused here, as fetch would quote it in its error.
    if (!/^[\x21-\x7e]+$/.test(this.#apiKey)) return new TransportError("unusable API key");
    const url = new URL(this.#baseUrl + request.path);
    for (const [key, value] of request.params) url.searchParams.append(key, value);
    // Called bare: browsers and Workers reject `fetch` with a receiver.
    const send = this.#fetch;
    try {
      const response = await send(url, {
        headers: { "X-API-Key": this.#apiKey },
        // A redirect would carry the key to another host, so it is refused.
        redirect: "error",
        signal: AbortSignal.timeout(this.#timeoutMs),
      });
      return decode(request, response.status, await response.text());
    } catch (error) {
      return new TransportError(reason(error));
    }
  }
}

function reason(error: unknown): string {
  if (!(error instanceof Error)) return String(error);
  const cause = error.cause instanceof Error ? `: ${error.cause.message}` : "";
  return `${error.message || error.name}${cause}`;
}
