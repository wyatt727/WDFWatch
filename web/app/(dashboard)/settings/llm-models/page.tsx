/**
 * LLM Models Settings Page
 * 
 * Allows users to configure which LLM models are used for each pipeline task:
 * - Summarization
 * - Few-shot generation
 * - Classification  
 * - Response generation
 * 
 * Related files:
 * - /web/app/api/settings/llm-models/route.ts (API endpoint)
 * - /web/components/settings/llm-models-form.tsx (Form component)
 */

import { Metadata } from 'next'
import { LLMModelsForm } from '@/components/settings/llm-models-form'

export const metadata: Metadata = {
  title: 'LLM Models - Settings',
  description: 'Configure LLM models for pipeline tasks',
}

export default function LLMModelsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">LLM Models</h1>
        <p className="text-muted-foreground mt-2">
          Configure which language models are used for each pipeline task. Choose models based on performance, cost, and capability requirements.
        </p>
      </div>

      <LLMModelsForm />
    </div>
  )
}