import { Client } from "ng-postcode-js/client";
import { expect, it, vi } from "vitest";
import { isAssigned, nipostClient } from "./nipost";

function answering(status: number, body: unknown) {
  const fetch = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  return new Client("test-key", { fetch });
}

const data = (status: string) => ({ data: { postcode: "FC-02-A09-DB-09", valid: status === "valid", status, verified: false } });

it.each([
  ["valid", true],
  ["not_found", false],
  ["invalid", false],
])("reads a %s answer", async (status, expected) => {
  expect(await isAssigned("FC-02-A09-DB-09", answering(200, data(status)))).toBe(expected);
});

it("cannot say when NIPOST refuses the key or is unreachable", async () => {
  vi.spyOn(console, "warn").mockImplementation(() => {});
  const refused = answering(401, { error: { code: "invalid_api_key", message: "bad key" } });
  expect(await isAssigned("FC-02-A09-DB-09", refused)).toBeNull();
  const offline = new Client("test-key", { fetch: () => Promise.reject(new TypeError("fetch failed")) });
  expect(await isAssigned("FC-02-A09-DB-09", offline)).toBeNull();
});

it("sends nothing for a malformed code", async () => {
  const fetch = vi.fn();
  expect(await isAssigned("100271", new Client("test-key", { fetch }))).toBe(false);
  expect(fetch).not.toHaveBeenCalled();
});

it("confirms codes only with a live key", () => {
  vi.spyOn(console, "warn").mockImplementation(() => {});
  expect(nipostClient()).toBeNull();
  expect(nipostClient(" ")).toBeNull();
  expect(nipostClient("nipost_pk_test_abc")).toBeNull();
  expect(nipostClient("nipost_test_abc")).toBeNull();
  expect(nipostClient("nipost_pk_live_abc")).toBeInstanceOf(Client);
});
