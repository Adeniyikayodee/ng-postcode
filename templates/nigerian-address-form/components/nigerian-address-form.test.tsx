import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { NigerianAddressForm } from "./nigerian-address-form";

afterEach(cleanup);

async function fill(postcode: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Full name"), "Ngozi Eze");
  await user.type(screen.getByLabelText("Phone number"), "0803 123 4567");
  await user.type(screen.getByLabelText("Street address"), "5 Aminu Kano Crescent");
  await user.type(screen.getByLabelText("Town or city"), "Wuse II");
  await user.selectOptions(screen.getByLabelText("State"), "Federal Capital Territory");
  if (postcode) await user.type(screen.getByLabelText(/^Postcode/), postcode);
  return user;
}

it("sends the address in canonical form", async () => {
  const onSubmit = vi.fn();
  render(<NigerianAddressForm onSubmit={onSubmit} />);
  const user = await fill("fc 02 a09 db 09");
  await user.click(screen.getByRole("button", { name: "Continue" }));
  expect(onSubmit).toHaveBeenCalledWith({
    name: "Ngozi Eze",
    phone: "+2348031234567",
    street: "5 Aminu Kano Crescent",
    city: "Wuse II",
    lga: "",
    state: "Federal Capital Territory",
    postcode: "FC-02-A09-DB-09",
  });
});

it("tidies the postcode when the customer leaves the field", async () => {
  render(<NigerianAddressForm onSubmit={vi.fn()} />);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/^Postcode/), "fc02a09db09");
  await user.tab();
  expect(screen.getByLabelText(/^Postcode/)).toHaveProperty("value", "FC-02-A09-DB-09");
});

it("offers a fix for look-alike characters", async () => {
  render(<NigerianAddressForm onSubmit={vi.fn()} />);
  const user = userEvent.setup();
  const input = screen.getByLabelText(/^Postcode/);
  await user.type(input, "FC-O2-A09-DB-O9");
  await user.tab();
  expect(input.getAttribute("aria-invalid")).toBe("true");
  await user.click(screen.getByRole("button", { name: "Use FC-02-A09-DB-09" }));
  expect(input).toHaveProperty("value", "FC-02-A09-DB-09");
  expect(input.getAttribute("aria-invalid")).toBeNull();
  expect(document.activeElement).toBe(input);
});

it("explains an old six-digit code and does not send it", async () => {
  const onSubmit = vi.fn();
  render(<NigerianAddressForm onSubmit={onSubmit} />);
  const user = await fill("100271");
  await user.click(screen.getByRole("button", { name: "Continue" }));
  expect(screen.getByRole("alert").textContent).toMatch(/old six-digit code/);
  expect(document.activeElement).toBe(screen.getByLabelText(/^Postcode/));
  expect(onSubmit).not.toHaveBeenCalled();
});

it("requires the postcode when asked to", async () => {
  render(<NigerianAddressForm onSubmit={vi.fn()} postcodeRequired />);
  const user = await fill("");
  await user.click(screen.getByRole("button", { name: "Continue" }));
  expect(screen.getByRole("alert").textContent).toBe("Enter your postcode.");
});

it("shows errors the server returns", async () => {
  render(<NigerianAddressForm onSubmit={async () => ({ postcode: "NIPOST has no building with this postcode." })} />);
  const user = await fill("FC-02-A09-DB-09");
  await user.click(screen.getByRole("button", { name: "Continue" }));
  expect((await screen.findByRole("alert")).textContent).toBe("NIPOST has no building with this postcode.");
});

it("says so when sending fails", async () => {
  render(<NigerianAddressForm onSubmit={() => Promise.reject(new Error("offline"))} />);
  const user = await fill("");
  await user.click(screen.getByRole("button", { name: "Continue" }));
  expect((await screen.findByRole("alert")).textContent).toBe("We could not send your address. Try again.");
});

it("clears an error once the customer edits the field", async () => {
  render(<NigerianAddressForm onSubmit={vi.fn()} />);
  const user = userEvent.setup();
  const input = screen.getByLabelText(/^Postcode/);
  await user.type(input, "100271");
  await user.tab();
  expect(screen.getByRole("alert").textContent).toMatch(/old six-digit code/);
  await user.type(input, "{Backspace}");
  expect(screen.queryByRole("alert")).toBeNull();
  await user.tab();
  expect(screen.getByRole("alert").textContent).toMatch(/A postcode has 11/);
});
