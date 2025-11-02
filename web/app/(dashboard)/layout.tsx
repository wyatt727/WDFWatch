/**
 * Dashboard layout with navigation sidebar and quota meter
 * Provides consistent layout for all dashboard pages
 * Interacts with: Navigation component, QuotaMeter component
 */

"use client"

import { Navigation } from "@/components/layout/Navigation"
import { QuotaMeter } from "@/components/layout/QuotaMeter"
import { QuotaMeterWrapper } from "@/components/layout/QuotaMeterWrapper"
import { Toaster } from "@/components/ui/toaster"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex h-screen">
      {/* Sidebar navigation */}
      <Navigation />
      
      {/* Main content area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar with quota meter */}
        <header className="border-b px-6 py-4 flex items-center justify-between">
          <h1 className="text-2xl font-semibold">WDFWatch</h1>
          <QuotaMeterWrapper />
        </header>
        
        {/* Page content */}
        <main className="flex-1 overflow-y-auto overflow-x-hidden p-6">
          {children}
        </main>
      </div>
      
      <Toaster />
    </div>
  )
}