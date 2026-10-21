"use client";

import { type FocusEvent, type FormEvent, useRef, useState, useSyncExternalStore, useTransition } from "react";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import {
  type Address,
  type AddressErrors,
  type AddressInput,
  addressSchema,
  checkPostcode,
  EXAMPLE,
  fieldErrors,
  STATES,
} from "@/lib/nigerian-address";

type Props = {
  /** Return field errors to show them, such as a postcode the server refused. */
  onSubmit: (address: Address) => Promise<AddressErrors | void> | AddressErrors | void;
  postcodeRequired?: boolean;
  submitLabel?: string;
};

type Name = keyof AddressInput;

const noop = () => () => {};

export function NigerianAddressForm({ onSubmit, postcodeRequired = false, submitLabel = "Continue" }: Props) {
  const form = useRef<HTMLFormElement>(null);
  const [errors, setErrors] = useState<AddressErrors>({});
  const [suggestion, setSuggestion] = useState<string>();
  const [failed, setFailed] = useState(false);
  const [pending, startTransition] = useTransition();
  // Until React runs, a click would submit the address as a plain GET.
  const ready = useSyncExternalStore(noop, () => true, () => false);

  function show(next: AddressErrors) {
    setErrors(next);
    const first = Object.keys(next)[0];
    if (first) form.current?.querySelector<HTMLElement>(`[name="${first}"]`)?.focus();
  }

  function checkOnBlur(event: FocusEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const check = input.value.trim() ? checkPostcode(input.value) : undefined;
    if (check?.ok) input.value = check.postcode;
    setSuggestion(check && !check.ok ? check.suggestion : undefined);
    setErrors(({ postcode: _, ...rest }) => (check && !check.ok ? { ...rest, postcode: check.error } : rest));
  }

  function applySuggestion() {
    const input = form.current?.elements.namedItem("postcode");
    if (input instanceof HTMLInputElement && suggestion) input.value = suggestion;
    setSuggestion(undefined);
    setErrors(({ postcode: _, ...rest }) => rest);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFailed(false);
    const result = addressSchema({ postcodeRequired }).safeParse(
      Object.fromEntries(new FormData(event.currentTarget)),
    );
    if (!result.success) return show(fieldErrors(result.error));
    setErrors({});
    startTransition(async () => {
      try {
        const refused = await onSubmit(result.data);
        if (refused) show(refused);
      } catch {
        setFailed(true);
      }
    });
  }

  function field(name: Name) {
    const error = errors[name];
    return {
      id: name,
      name,
      "aria-invalid": error ? true : undefined,
      "aria-describedby": error ? `${name}-error` : undefined,
    };
  }

  function error(name: Name) {
    return errors[name] && <FieldError id={`${name}-error`}>{errors[name]}</FieldError>;
  }

  return (
    <form ref={form} onSubmit={submit} noValidate aria-busy={pending}>
      <FieldGroup>
        <Field data-invalid={!!errors.name}>
          <FieldLabel htmlFor="name">Full name</FieldLabel>
          <Input {...field("name")} autoComplete="name" />
          {error("name")}
        </Field>
        <Field data-invalid={!!errors.phone}>
          <FieldLabel htmlFor="phone">Phone number</FieldLabel>
          <Input {...field("phone")} type="tel" autoComplete="tel" inputMode="tel" placeholder="0803 123 4567" />
          {error("phone")}
        </Field>
        <Field data-invalid={!!errors.street}>
          <FieldLabel htmlFor="street">Street address</FieldLabel>
          <Input {...field("street")} autoComplete="street-address" />
          {error("street")}
        </Field>
        <Field data-invalid={!!errors.city}>
          <FieldLabel htmlFor="city">Town or city</FieldLabel>
          <Input {...field("city")} autoComplete="address-level2" />
          {error("city")}
        </Field>
        <Field data-invalid={!!errors.lga}>
          <FieldLabel htmlFor="lga">Local government area (optional)</FieldLabel>
          <Input {...field("lga")} />
          {error("lga")}
        </Field>
        <Field data-invalid={!!errors.state}>
          <FieldLabel htmlFor="state">State</FieldLabel>
          <NativeSelect {...field("state")} autoComplete="address-level1" defaultValue="" className="w-full">
            <NativeSelectOption value="" disabled>
              Choose a state
            </NativeSelectOption>
            {STATES.map((state) => (
              <NativeSelectOption key={state} value={state}>
                {state}
              </NativeSelectOption>
            ))}
          </NativeSelect>
          {error("state")}
        </Field>
        <Field data-invalid={!!errors.postcode}>
          <FieldLabel htmlFor="postcode">Postcode{postcodeRequired ? "" : " (optional)"}</FieldLabel>
          <Input
            {...field("postcode")}
            autoComplete="postal-code"
            autoCapitalize="characters"
            autoCorrect="off"
            spellCheck={false}
            maxLength={24}
            placeholder={EXAMPLE}
            onBlur={checkOnBlur}
          />
          <FieldDescription>
            The 11-character NIPOST postcode. Find yours at{" "}
            <a href="https://postcode.gov.ng/find" target="_blank" rel="noreferrer">
              postcode.gov.ng
            </a>
            .
          </FieldDescription>
          {error("postcode")}
          {suggestion && (
            <Button type="button" variant="outline" size="sm" className="w-fit" onClick={applySuggestion}>
              Use {suggestion}
            </Button>
          )}
        </Field>
        {failed && <FieldError>We could not send your address. Try again.</FieldError>}
        <Button type="submit" disabled={!ready || pending}>
          {pending ? "Sending…" : submitLabel}
        </Button>
      </FieldGroup>
    </form>
  );
}
