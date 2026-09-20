import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AcadTrack — University of Loralai",
  description: "Enterprise GPA Management System",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
