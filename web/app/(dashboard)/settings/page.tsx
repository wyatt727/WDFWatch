/**
 * Settings Index Page
 * 
 * Provides navigation to all settings sections
 * 
 * Related files:
 * - /web/app/(dashboard)/settings/[section]/page.tsx (Settings subpages)
 */

import { Metadata } from 'next'
import Link from 'next/link'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { 
  Key, 
  Search, 
  Sliders, 
  ChevronRight,
  Shield,
  Zap,
  Globe,
  Brain,
  FileText,
  BarChart3
} from 'lucide-react'

export const metadata: Metadata = {
  title: 'Settings',
  description: 'Configure WDFWatch settings',
}

const settingsSections = [
  {
    title: 'API Keys',
    description: 'Configure external API keys for Twitter, Gemini, and other services',
    href: '/settings/api-keys',
    icon: Key,
    color: 'text-orange-500',
  },
  {
    title: 'LLM Models',
    description: 'Configure which language models are used for each pipeline task',
    href: '/settings/llm-models',
    icon: Brain,
    color: 'text-purple-500',
  },
  {
    title: 'Prompts & Context',
    description: 'Customize LLM prompts and context files for all pipeline stages',
    href: '/settings/prompts',
    icon: FileText,
    color: 'text-indigo-500',
  },
  {
    title: 'Keywords',
    description: 'Manage search keywords for tweet discovery',
    href: '/settings/keywords',
    icon: Search,
    color: 'text-blue-500',
  },
  {
    title: 'Scoring Thresholds',
    description: 'Configure relevancy scoring thresholds for tweet classification',
    href: '/settings/scoring',
    icon: BarChart3,
    color: 'text-amber-500',
  },
  {
    title: 'Scraping Configuration',
    description: 'Configure tweet scraping parameters and filters',
    href: '/settings/scraping',
    icon: Sliders,
    color: 'text-green-500',
  },
]

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-muted-foreground mt-2">
          Configure WDFWatch to work the way you want
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {settingsSections.map((section) => (
          <Link key={section.href} href={section.href}>
            <Card className="h-full hover:shadow-lg transition-shadow cursor-pointer">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <section.icon className={`h-5 w-5 ${section.color}`} />
                      <CardTitle className="text-lg">{section.title}</CardTitle>
                    </div>
                    <CardDescription>{section.description}</CardDescription>
                  </div>
                  <ChevronRight className="h-5 w-5 text-muted-foreground" />
                </div>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>

      <div className="mt-8 p-4 rounded-lg border bg-muted/50">
        <div className="flex items-center gap-2 mb-2">
          <Shield className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-medium">Security Note</h3>
        </div>
        <p className="text-sm text-muted-foreground">
          All sensitive data including API keys are encrypted before storage. 
          Make sure to keep your encryption key secure in production environments.
        </p>
      </div>
    </div>
  )
}