/**
 * Navigation component for dashboard sidebar
 * Provides navigation links to all dashboard sections
 * Interacts with: Dashboard layout, Next.js routing
 */

"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import {
  Home,
  MessageSquare,
  CheckSquare,
  BarChart3,
  Settings,
  Podcast,
  Twitter,
  Activity,
  List,
  Link as LinkIcon,
  AlertTriangle,
  Search,
} from "lucide-react"

const navigation = [
  {
    name: "Dashboard",
    href: "/",
    icon: Home,
  },
  {
    name: "Tweet Inbox",
    href: "/inbox",
    icon: Twitter,
  },
  {
    name: "Draft Review",
    href: "/review",
    icon: CheckSquare,
  },
  {
    name: "Tweet Queue",
    href: "/tweet-queue",
    icon: List,
  },
  {
    name: "Single Tweet",
    href: "/single-tweet",
    icon: LinkIcon,
  },
  {
    name: "Manual Scrape",
    href: "/manual-scrape",
    icon: Search,
  },
  {
    name: "Episodes",
    href: "/episodes",
    icon: Podcast,
  },
  {
    name: "Monitoring",
    href: "/monitoring",
    icon: AlertTriangle,
  },
  {
    name: "Analytics",
    href: "/analytics",
    icon: BarChart3,
  },
  {
    name: "Audit Logs",
    href: "/audit",
    icon: Activity,
  },
  {
    name: "Settings",
    href: "/settings",
    icon: Settings,
  },
]

export function Navigation() {
  const pathname = usePathname()

  return (
    <nav className="w-64 border-r bg-card h-full">
      {/* Logo/Brand */}
      <div className="p-6 border-b">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-6 w-6 text-primary" />
          <span className="text-xl font-bold">WDFWatch</span>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          AI-Powered Social Engagement
        </p>
      </div>

      {/* Navigation Links */}
      <div className="p-4 space-y-1">
        {navigation.map((item) => {
          const isActive = pathname === item.href
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.name}
            </Link>
          )
        })}
      </div>

      {/* Pipeline Status (optional) */}
      <div className="mt-auto p-4 border-t">
        <div className="p-3 rounded-lg bg-muted">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium">Pipeline Status</span>
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          </div>
          <p className="text-xs text-muted-foreground">
            Last run: 5 minutes ago
          </p>
        </div>
      </div>
    </nav>
  )
}