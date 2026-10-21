# Nigerian address form

A React checkout address form for Nigeria that accepts the 11-character NIPOST digital postcode (NDAPS), such as `FC-02-A09-DB-09`. It is built with [shadcn/ui](https://ui.shadcn.com) and [`ng-postcode-js`](https://www.npmjs.com/package/ng-postcode-js), and this folder is a Next.js app that uses it.

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2FAdeniyikayodee%2Fng-postcode%2Ftree%2Fmain%2Ftemplates%2Fnigerian-address-form&project-name=nigerian-address-form)
[![Open in v0](https://v0.app/chat-static/button.svg)](https://v0.app/chat/api/open?url=https%3A%2F%2Fadeniyikayodee.github.io%2Fng-postcode%2Fr%2Fnigerian-address-form.json)

## Add it to your project

In a project set up with shadcn/ui:

```sh
npx shadcn@latest add https://adeniyikayodee.github.io/ng-postcode/r/nigerian-address-form.json
```

```tsx
import { NigerianAddressForm } from "@/components/nigerian-address-form";

<NigerianAddressForm onSubmit={saveAddress} postcodeRequired={false} />;
```

`onSubmit` receives the address with the postcode as `FC-02-A09-DB-09` and the phone number as `+2348031234567`. Return field errors, such as `{ postcode: "..." }`, to show them on the form.

Check the address again on the server, since the browser's check can be skipped:

```ts
import { addressSchema, fieldErrors } from "@/lib/nigerian-address";

const result = addressSchema().safeParse(input);
if (!result.success) return fieldErrors(result.error);
```

## What it handles

- Hyphens, spaces, no separator, and either case: the postcode is tidied to `FC-02-A09-DB-09` when the customer leaves the field.
- Look-alike characters, such as `O` for `0`, with a one-tap fix the customer confirms.
- An old six-digit code, with a message that shows the new format.
- Errors in plain words, linked to their field for screen readers, with focus moved to the first one.
- Browser autofill, through the standard `autocomplete` names and a native state picker.
- Optional confirmation with NIPOST: set `NG_POSTCODE_API_KEY` to a live key from the [NIPOST developer dashboard](https://dashboard.postcode.gov.ng), and the server refuses codes NIPOST has not assigned. If NIPOST is slow or unreachable, the order goes through on the offline check. Test keys answer "not found" for every code, so they are ignored.

## Run it

```sh
npm install
npm run dev
```

`npm test` runs the tests, and `npm run registry` rebuilds the published registry item in `docs/r`.
