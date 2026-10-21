"use client";

import {
  type FocusEvent,
  type FormEvent,
  type ReactNode,
  useRef,
  useState,
  useSyncExternalStore,
  useTransition,
} from "react";
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

// Plain elements styled with the shadcn theme, so the form needs no other component
// and installs the same in every shadcn style and in v0.
const control =
  "h-9 w-full rounded-md border border-input bg-transparent px-3 text-base outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 aria-invalid:border-destructive aria-invalid:ring-destructive/20 md:text-sm dark:bg-input/30";
const button =
  "inline-flex h-9 items-center justify-center rounded-md px-4 text-sm font-medium outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50";

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
    if (!input.value.trim()) return;
    const check = checkPostcode(input.value);
    if (check.ok) {
      input.value = check.postcode;
      return;
    }
    setSuggestion(check.suggestion);
    setErrors((current) => ({ ...current, postcode: check.error }));
  }

  // Cleared on edit, not on blur: a message vanishing as the customer clicks
  // "Place order" moves the button out from under the pointer.
  function clearOnEdit(event: FormEvent<HTMLFormElement>) {
    const { name } = event.target as HTMLInputElement;
    if (name === "postcode") setSuggestion(undefined);
    setErrors((current) => {
      if (!(name in current)) return current;
      const { [name as Name]: _, ...rest } = current;
      return rest;
    });
  }

  function applySuggestion() {
    const input = form.current?.elements.namedItem("postcode");
    if (input instanceof HTMLInputElement && suggestion) {
      input.value = suggestion;
      // The button that had focus is about to go away.
      input.focus();
    }
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
    const message = errors[name];
    if (!message) return null;
    // Keep the example code on one line.
    const [before, after] = message.split(EXAMPLE);
    return (
      <p id={`${name}-error`} role="alert" className="text-sm text-destructive">
        {after === undefined ? message : <>{before}<span className="whitespace-nowrap">{EXAMPLE}</span>{after}</>}
      </p>
    );
  }

  function row(name: Name, label: string, input: ReactNode, extra?: ReactNode) {
    return (
      <div className="grid gap-2">
        <label htmlFor={name} className="text-sm font-medium">
          {label}
        </label>
        {input}
        {extra}
        {error(name)}
      </div>
    );
  }

  return (
    <form ref={form} onSubmit={submit} onChange={clearOnEdit} noValidate aria-busy={pending} className="grid gap-5">
      {row("name", "Full name", <input {...field("name")} autoComplete="name" className={control} />)}
      {row(
        "phone",
        "Phone number",
        <input {...field("phone")} type="tel" autoComplete="tel" inputMode="tel" placeholder="0803 123 4567" className={control} />,
      )}
      {row("street", "Street address", <input {...field("street")} autoComplete="street-address" className={control} />)}
      {row("city", "Town or city", <input {...field("city")} autoComplete="address-level2" className={control} />)}
      {row("lga", "Local government area (optional)", <input {...field("lga")} className={control} />)}
      {row(
        "state",
        "State",
        <select {...field("state")} autoComplete="address-level1" defaultValue="" className={control}>
          <option value="" disabled>
            Choose a state
          </option>
          {STATES.map((state) => (
            <option key={state} value={state}>
              {state}
            </option>
          ))}
        </select>,
      )}
      {row(
        "postcode",
        `Postcode${postcodeRequired ? "" : " (optional)"}`,
        <input
          {...field("postcode")}
          autoComplete="postal-code"
          autoCapitalize="characters"
          autoCorrect="off"
          spellCheck={false}
          maxLength={24}
          placeholder={EXAMPLE}
          onBlur={checkOnBlur}
          className={control}
        />,
        <p className="text-sm text-muted-foreground">
          The 11-character NIPOST postcode. Find yours at{" "}
          <a href="https://postcode.gov.ng/find" target="_blank" rel="noreferrer" className="underline">
            postcode.gov.ng
          </a>
          .
        </p>,
      )}
      {suggestion && (
        <button type="button" onClick={applySuggestion} className={`${button} -mt-3 w-fit border border-input`}>
          Use {suggestion}
        </button>
      )}
      {failed && (
        <p role="alert" className="text-sm text-destructive">
          We could not send your address. Try again.
        </p>
      )}
      <button type="submit" disabled={!ready || pending} className={`${button} bg-primary text-primary-foreground`}>
        {pending ? "Sending…" : submitLabel}
      </button>
    </form>
  );
}
