"use server";

import { redirect } from "next/navigation";
import { type AddressErrors, addressSchema, fieldErrors } from "@/lib/nigerian-address";

/** The browser's check can be skipped, so the server checks again. */
export async function placeOrder(input: unknown): Promise<AddressErrors> {
  const result = addressSchema().safeParse(input);
  if (!result.success) return fieldErrors(result.error);
  // Save result.data with the order here.
  redirect("/thanks");
}
