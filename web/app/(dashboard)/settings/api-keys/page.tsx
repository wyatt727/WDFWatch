/**
 * API Keys Settings Page
 * 
 * Allows users to configure external API keys for:
 * - Twitter/X API
 * - Google Gemini API
 * - OpenAI API (future)
 * 
 * Related files:
 * - /web/app/api/settings/api-keys/route.ts (API endpoint)
 * - /web/components/settings/api-keys-form.tsx (Form component)
 */

import { Metadata } from 'next'
import { ApiKeysForm } from '@/components/settings/api-keys-form'

export const metadata: Metadata = {
  title: 'API Keys - Settings',
  description: 'Configure external API keys',
}

export default function ApiKeysPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">API Keys</h1>
        <p className="text-muted-foreground mt-2">
          Configure API keys for external services. Keys are encrypted before storage.
        </p>
      </div>

      <ApiKeysForm />
    </div>
  )
}