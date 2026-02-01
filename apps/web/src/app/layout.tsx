import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Aave Risk Monitor",
  description: "Aave v3 risk monitoring dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
