"use server";

import { redirect } from "next/navigation";
import { type AddressErrors, addressSchema, fieldErrors } from "@/lib/nigerian-address";
import { isAssigned, nipostClient } from "@/lib/nipost";

const nipost = nipostClient(process.env.NG_POSTCODE_API_KEY);

/** The browser's check can be skipped, so the server checks again. */
export async function placeOrder(input: unknown): Promise<AddressErrors> {
  const result = addressSchema().safeParse(input);
  if (!result.success) return fieldErrors(result.error);
  const { postcode } = result.data;
  if (postcode && nipost && (await isAssigned(postcode, nipost)) === false) {
    return { postcode: "NIPOST has no building with this postcode. Check it at postcode.gov.ng/find." };
  }
  // Save result.data with the order here.
  redirect("/thanks");
}
