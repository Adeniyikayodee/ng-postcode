import { describe, expect, it } from "vitest";
import { addressSchema, checkPostcode, fieldErrors, normalisePhone } from "./nigerian-address";

const address = {
  name: "Ngozi Eze",
  phone: "0803 123 4567",
  street: "5 Aminu Kano Crescent",
  city: "Wuse II",
  lga: "",
  state: "Federal Capital Territory",
  postcode: "fc 02 a09 db 09",
};

describe("checkPostcode", () => {
  it.each(["FC-02-A09-DB-09", "fc 02 a09 db 09", "FC02A09DB09", " FC-02-A09-DB-09 "])(
    "accepts %s in its canonical form",
    (text) => expect(checkPostcode(text)).toEqual({ ok: true, postcode: "FC-02-A09-DB-09" }),
  );

  it("suggests a fix for look-alike characters", () => {
    expect(checkPostcode("FC-O2-A09-DB-O9")).toEqual({
      ok: false,
      error: "Check your postcode.",
      suggestion: "FC-02-A09-DB-09",
    });
  });

  it.each([
    ["100271", "That is the old six-digit code. The new postcode looks like FC-02-A09-DB-09."],
    ["FC-02-A09", "A postcode has 11 letters and digits, such as FC-02-A09-DB-09."],
    ["FC-00-A09-DB-09", "Characters 3 and 4 must be digits from 01 to 99."],
    ["FC-02-A09-D4-09", "Characters 8 and 9 must be letters."],
    ["FC-02-A09-DB-00", "The last two characters must be digits from 01 to 99."],
    ["FC_02_A09_DB_09", "Use only letters, digits, spaces and hyphens."],
  ])("explains why %s is wrong", (text, error) => {
    expect(checkPostcode(text)).toEqual({ ok: false, error });
  });
});

describe("normalisePhone", () => {
  it.each(["0803 123 4567", "+234 803 123 4567", "2348031234567", "(0803) 123-4567"])(
    "reads %s",
    (text) => expect(normalisePhone(text)).toBe("+2348031234567"),
  );

  it.each(["0803 123 456", "0603 123 4567", "+44 7700 900123", ""])("refuses %s", (text) => {
    expect(normalisePhone(text)).toBeNull();
  });
});

describe("addressSchema", () => {
  it("returns the address in canonical form", () => {
    expect(addressSchema().parse(address)).toEqual({
      ...address,
      phone: "+2348031234567",
      postcode: "FC-02-A09-DB-09",
    });
  });

  it("allows an empty postcode unless it is required", () => {
    const empty = { ...address, postcode: " " };
    expect(addressSchema().parse(empty).postcode).toBe("");
    const result = addressSchema({ postcodeRequired: true }).safeParse(empty);
    expect(result.success || fieldErrors(result.error)).toEqual({ postcode: "Enter your postcode." });
  });

  it("names the first problem in each field", () => {
    const result = addressSchema().safeParse({ ...address, state: "Lagos State", postcode: "100271" });
    expect(result.success || fieldErrors(result.error)).toEqual({
      state: "Choose your state.",
      postcode: "That is the old six-digit code. The new postcode looks like FC-02-A09-DB-09.",
    });
  });

  it("refuses values that are not text", () => {
    const result = addressSchema().safeParse({ ...address, postcode: 12345678901 });
    expect(result.success).toBe(false);
  });
});
