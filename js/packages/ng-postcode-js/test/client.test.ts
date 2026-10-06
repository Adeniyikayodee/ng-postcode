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
  expect(seen?.[1]).toMatchObject({ headers: { "X-API-Key": "secret" }, redirect: "error" });
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
  expect(String(refused) + String(unreachable) + String(slow)).not.toContain("secret");
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
