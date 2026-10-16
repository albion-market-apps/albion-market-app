import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import "./globals.css";
import { LocaleSwitcher } from "./locale-switcher";

export const metadata: Metadata = {
  title: "Albion Market Tracker",
  description: "Rastreador de preços do mercado de Albion Online",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale}>
      <body className="min-h-screen bg-slate-950 text-slate-100">
        <NextIntlClientProvider locale={locale} messages={messages}>
          <header className="flex justify-end p-4">
            <LocaleSwitcher />
          </header>
          <main className="mx-auto max-w-2xl px-4 pb-16">{children}</main>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
