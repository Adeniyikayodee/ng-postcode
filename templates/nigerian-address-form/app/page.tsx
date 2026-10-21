import { NigerianAddressForm } from "@/components/nigerian-address-form";
import { placeOrder } from "./actions";

export default function Home() {
  return (
    <main className="mx-auto max-w-lg px-4 py-10">
      <h1 className="mb-6 text-2xl font-semibold">Delivery address</h1>
      <NigerianAddressForm onSubmit={placeOrder} submitLabel="Place order" />
    </main>
  );
}
