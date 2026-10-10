import { createServer } from "node:http";
import type { AddressInfo } from "node:net";
import { expect, test } from "vitest";
import { ApiError, lookup } from "../src/api.js";
import { Client, TransportError } from "../src/client.js";
import { type Postcode, parse } from "../src/postcode.js";

const CODE = parse("FC03B06AG12") as Postcode;

function client(respond: (url: URL, init: RequestInit) => Response | Promise<Response>): Client {
  const fake = ((url: URL, init: RequestInit) =>
    Promise.resolve(respond(url, init))) as typeof fetch;
  return new Client("secret", { fetch: fake, timeoutMs: 50 });
}

// spec/client.json: sends_the_key, refuses_redirects
test("sends the key and query, refuses redirects, and decodes the answer", async () => {
  let seen: [string, RequestInit] | undefined;
  const found = await client((url, init) => {
    seen = [String(url), init];
    return Response.json({ data: { postcode: "FC-03-B06-AG-12", valid: true } });
  }).send(lookup(CODE, 2));
  expect(found).toMatchObject({ valid: true });
  expect(seen?.[0]).toBe("https://api.postcode.gov.ng/v1/lookup?code=FC-03-B06-AG-12&level=2");
  expect(seen?.[1]).toMatchObject({ headers: { "X-API-Key": "secret" }, redirect: "manual" });
});

test("a redirect is not followed, and reads as a malformed answer", async () => {
  let served = 0;
  const server = createServer((_, response) => {
    served += 1;
    response.writeHead(302, { Location: "/elsewhere" }).end();
  }).listen(0, "127.0.0.1");
  await new Promise((resolve) => server.once("listening", resolve));
  const baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  const refused = await new Client("secret", { baseUrl }).send(lookup(CODE));
  server.close();
  expect(refused).toMatchObject({ status: 302, code: "malformed_response" });
  expect(served).toBe(1);
});

// spec/client.json: ignores_a_trailing_slash
test("a trailing slash on the base URL is ignored", async () => {
  let seen = "";
  const fake = ((url: URL) => {
    seen = String(url);
    return Promise.resolve(Response.json({ data: { valid: true } }));
  }) as typeof fetch;
  await new Client("secret", { baseUrl: "https://staging.example//", fetch: fake }).send(
    lookup(CODE),
  );
  expect(seen).toBe("https://staging.example/v1/lookup?code=FC-03-B06-AG-12&level=1");
});

// spec/client.json: failures_are_values
test("failures are values, and never carry the key", async () => {
  const refused = await client(() =>
    Response.json({ error: { code: "invalid_api_key", message: "no" } }, { status: 401 }),
  ).send(lookup(CODE));
  expect(refused).toBeInstanceOf(ApiError);

  const unreachable = await client(() => {
    throw new TypeError("fetch failed", { cause: new Error("getaddrinfo ENOTFOUND") });
  }).send(lookup(CODE));
  expect(unreachable).toBeInstanceOf(TransportError);
  expect(String(unreachable)).toBe("fetch failed: getaddrinfo ENOTFOUND");

  const slow = await client(
    (_, init) =>
      new Promise((_, reject) =>
        init.signal?.addEventListener("abort", () => reject(init.signal?.reason)),
      ),
  ).send(lookup(CODE));
  expect(slow).toBeInstanceOf(TransportError);

  const nowhere = await new Client("secret", { baseUrl: "http://[::1" }).send(lookup(CODE));
  expect(nowhere).toBeInstanceOf(TransportError);
  expect(String(refused) + String(unreachable) + String(slow)).not.toContain("secret");
});

// spec/client.json: refuses_an_unusable_key
test.each(["se\ncret", "se cret", "sécret", "", " \n"])(
  "an unusable key %j is refused without being echoed",
  async (key) => {
    let sent = 0;
    const fake = (() => {
      sent += 1;
      return Promise.resolve(new Response());
    }) as typeof fetch;
    const refused = await new Client(key, { fetch: fake }).send(lookup(CODE));
    expect(refused).toEqual(new TransportError("unusable API key"));
    expect(sent).toBe(0);
  },
);

test("whitespace around a key is dropped", async () => {
  let headers: unknown;
  const fake = ((_: URL, init: RequestInit) => {
    headers = init.headers;
    return Promise.resolve(Response.json({ data: { postcode: "FC-03-B06-AG-12", valid: true } }));
  }) as typeof fetch;
  await new Client(" secret\n", { fetch: fake }).send(lookup(CODE));
  expect(headers).toEqual({ "X-API-Key": "secret" });
});

test("calls fetch without a receiver, as browsers and Workers require", async () => {
  let receiver: unknown = "unset";
  const fake = function (this: unknown) {
    receiver = this;
    return Promise.resolve(Response.json({ data: { postcode: "FC-03-B06-AG-12", valid: true } }));
  } as typeof fetch;
  await new Client("secret", { fetch: fake }).send(lookup(CODE));
  expect(receiver).toBeUndefined();
});

test.each([0, -1, Number.NaN, Number.POSITIVE_INFINITY, "5"])(
  "a timeout of %j is refused",
  (timeoutMs) => {
    expect(() => new Client("secret", { timeoutMs: timeoutMs as number })).toThrow(RangeError);
  },
);

// spec/client.json: caps_the_body
test("a body over the cap is refused without being read in full", async () => {
  let served = 0;
  const flood = new ReadableStream<Uint8Array>({
    pull(controller) {
      served += 65536;
      controller.enqueue(new Uint8Array(65536).fill(32));
    },
  });
  const refused = await client(() => new Response(flood)).send(lookup(CODE));
  expect(refused).toEqual(new TransportError("response too large"));
  expect(served).toBeLessThan(4_000_000);
});

// spec/client.json: times_out_a_stalled_body
test("a body that stalls times out", async () => {
  const server = createServer((_, response) => {
    response.writeHead(200, { "Content-Length": 100 });
    response.write('{"data":');
  }).listen(0, "127.0.0.1");
  await new Promise((resolve) => server.once("listening", resolve));
  const baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  const stalled = await new Client("secret", { baseUrl, timeoutMs: 100 }).send(lookup(CODE));
  server.closeAllConnections();
  server.close();
  expect(stalled).toBeInstanceOf(TransportError);
});
