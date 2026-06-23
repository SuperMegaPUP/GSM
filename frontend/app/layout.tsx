import type { Metadata } from "next";
import "./globals.css";
import { Toaster } from "sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider, themeScript } from "@/components/ui/gsm/ThemeProvider";

export const metadata: Metadata = {
  title: "GSM — Подбор моторных масел",
  description: "B2B SaaS для подбора моторных масел с AI-консультантом",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" data-theme="industrial-warm">
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="antialiased font-sans">
        <TooltipProvider>
          <ThemeProvider>
            {children}
            <Toaster position="top-right" richColors />
          </ThemeProvider>
        </TooltipProvider>
      </body>
    </html>
  );
}
