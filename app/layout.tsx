import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "AI Foundations — Daily Audio Course",
    template: "%s | AI Foundations",
  },
  description:
    "Short daily AI lessons connected to the AI Foundations email course and Kindle library.",
  icons: {
    icon: "/podcast-cover.png",
    apple: "/podcast-cover.png",
  },
  openGraph: {
    title: "AI Foundations — Daily Audio Course",
    description:
      "Listen to the same daily lesson from the email course and Kindle library.",
    images: ["/podcast-cover.png"],
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
