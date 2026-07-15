import type { Metadata } from "next";
import { ApiKeyProvider } from "@/lib/api-key-context";
import "./globals.css";

export const metadata: Metadata = {
  title: "Debrief",
  description: "Self-hostable flight recorder + quality grader for LLM applications.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <ApiKeyProvider>{children}</ApiKeyProvider>
      </body>
    </html>
  );
}
