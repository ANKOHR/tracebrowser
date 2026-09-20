import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TraceBrowser | Replayable browser automation",
  description: "A deterministic browser runtime with evidence for every action.",
  openGraph: {
    title: "TraceBrowser",
    description: "Reliable, replayable browser automation with evidence for every action.",
    type: "website",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
