import { InvalidSegment, parse, parseLenient, Postcode, type Segment, WrongLength } from "ng-postcode-js";
import { z } from "zod";

export const STATES = [
  "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue", "Borno",
  "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu", "Federal Capital Territory",
  "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos",
  "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers", "Sokoto",
  "Taraba", "Yobe", "Zamfara",
] as const;

/** NIPOST's own example code. */
export const EXAMPLE = "FC-02-A09-DB-09";

const SEGMENT_HINTS: Record<Segment, string> = {
  state: "The first two characters must be letters.",
  lga: "Characters 3 and 4 must be digits from 01 to 99.",
  district: "Characters 5 to 7 must be letters or digits.",
  area: "Characters 8 and 9 must be letters.",
  unit: "The last two characters must be digits from 01 to 99.",
};

export type PostcodeCheck =
  | { ok: true; postcode: string }
  | { ok: false; error: string; suggestion?: string };

/** Check a typed postcode and say what is wrong in words a customer understands. */
export function checkPostcode(text: string): PostcodeCheck {
  const code = parse(text);
  if (code instanceof Postcode) return { ok: true, postcode: String(code) };
  if (/^\s*\d{6}\s*$/.test(text)) {
    return { ok: false, error: `That is the old six-digit code. The new postcode looks like ${EXAMPLE}.` };
  }
  const fixed = parseLenient(text);
  if ("postcode" in fixed) {
    return { ok: false, error: "Check your postcode.", suggestion: String(fixed.postcode) };
  }
  if (code instanceof WrongLength) {
    return { ok: false, error: `A postcode has 11 letters and digits, such as ${EXAMPLE}.` };
  }
  if (code instanceof InvalidSegment) return { ok: false, error: SEGMENT_HINTS[code.segment] };
  return { ok: false, error: "Use only letters, digits, spaces and hyphens." };
}

/** A Nigerian mobile number as +234 and ten digits, or null. */
export function normalisePhone(text: string): string | null {
  const match = /^(?:\+?234|0)([789][01]\d{8})$/.exec(text.replace(/[\s().-]/g, ""));
  return match ? `+234${match[1]}` : null;
}

export function addressSchema({ postcodeRequired = false } = {}) {
  return z.object({
    name: z.string().trim().min(2, "Enter your full name.").max(100),
    phone: z
      .string()
      .max(30)
      .transform((value, ctx) => {
        const phone = normalisePhone(value);
        if (phone) return phone;
        ctx.addIssue({ code: "custom", message: "Enter a Nigerian mobile number, such as 0803 123 4567." });
        return z.NEVER;
      }),
    street: z.string().trim().min(3, "Enter your street address.").max(200),
    city: z.string().trim().min(2, "Enter your town or city.").max(100),
    lga: z.string().trim().max(100),
    state: z.enum(STATES, { error: "Choose your state." }),
    postcode: z
      .string()
      .trim()
      .max(40)
      .transform((value, ctx) => {
        if (!value) {
          if (postcodeRequired) ctx.addIssue({ code: "custom", message: "Enter your postcode." });
          return "";
        }
        const check = checkPostcode(value);
        if (check.ok) return check.postcode;
        ctx.addIssue({ code: "custom", message: check.error });
        return z.NEVER;
      }),
  });
}

export type AddressSchema = ReturnType<typeof addressSchema>;
export type AddressInput = z.input<AddressSchema>;
export type Address = z.output<AddressSchema>;
export type AddressErrors = Partial<Record<keyof AddressInput, string>>;

/** The first error for each field. */
export function fieldErrors(error: z.ZodError<AddressInput>): AddressErrors {
  const { fieldErrors } = z.flattenError(error);
  return Object.fromEntries(
    Object.entries(fieldErrors).map(([field, messages]) => [field, messages?.[0]]),
  );
}
