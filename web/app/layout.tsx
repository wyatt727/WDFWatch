/**
 * Root layout for WDFWatch Web UI
 * Provides theme support, font loading, and global providers
 * Interacts with: globals.css, providers.tsx
 */

import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import { Providers } from "./providers"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "WDFWatch - Tweet Pipeline Manager",
  description: "AI-powered social media engagement pipeline for the War, Divorce, or Federalism podcast",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}