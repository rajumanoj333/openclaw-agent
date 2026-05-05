import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Morpheus — Marketing Agent",
  description: "AI marketing employee for your business — chat, voice, and Instagram in one place.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
