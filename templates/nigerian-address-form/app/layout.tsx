import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nigerian address form",
  description: "A checkout address form that accepts Nigeria's NIPOST digital postcode.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en-NG" className="h-full antialiased">
      <body className="min-h-full">{children}</body>
    </html>
  );
}
