/**
 * Keywords Settings Page
 * 
 * Dedicated page for keyword management
 * Provides direct access to the KeywordManager component
 * 
 * Related files:
 * - /web/components/keywords/KeywordManager.tsx (Main component)
 * - /web/app/(dashboard)/settings/scraping/page.tsx (Scraping settings)
 */

import { KeywordManager } from '@/components/keywords/KeywordManager'

export default function KeywordsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Keyword Management</h1>
        <p className="text-muted-foreground">
          Manage search keywords used for discovering relevant tweets
        </p>
      </div>

      <KeywordManager />
    </div>
  )
}