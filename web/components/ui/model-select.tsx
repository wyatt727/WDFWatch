/**
 * Model Select Component
 * 
 * A searchable select component optimized for large lists of LLM models
 * Groups models by provider and supports filtering
 * 
 * Used by: /components/settings/llm-models-form.tsx
 */

'use client'

import * as React from 'react'
import { Check, ChevronsUpDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { Badge } from '@/components/ui/badge'

export type ModelOption = {
  value: string
  label: string
  provider: string
  description: string
}

interface ModelSelectProps {
  models: ModelOption[]
  value: string
  onValueChange: (value: string) => void
  placeholder?: string
}

export function ModelSelect({
  models,
  value,
  onValueChange,
  placeholder = "Select a model...",
}: ModelSelectProps) {
  const [open, setOpen] = React.useState(false)
  const [search, setSearch] = React.useState('')

  // Group models by provider
  const groupedModels = React.useMemo(() => {
    const groups: Record<string, ModelOption[]> = {}
    
    // Handle undefined or empty models array
    if (!models || !Array.isArray(models)) {
      return groups
    }
    
    models.forEach(model => {
      if (!groups[model.provider]) {
        groups[model.provider] = []
      }
      groups[model.provider].push(model)
    })
    
    // Sort providers to show in consistent order
    const sortedGroups: Record<string, ModelOption[]> = {}
    const providerOrder = ['claude', 'gemini', 'openai', 'ollama']
    
    providerOrder.forEach(provider => {
      if (groups[provider]) {
        sortedGroups[provider] = groups[provider]
      }
    })
    
    // Add any remaining providers
    Object.keys(groups).forEach(provider => {
      if (!sortedGroups[provider]) {
        sortedGroups[provider] = groups[provider]
      }
    })
    
    return sortedGroups
  }, [models])

  const selectedModel = models?.find(m => m.value === value)

  // Filter models based on search
  const filteredGroups = React.useMemo(() => {
    if (!search) return groupedModels
    
    const filtered: Record<string, ModelOption[]> = {}
    const searchLower = search.toLowerCase()
    
    Object.entries(groupedModels).forEach(([provider, models]) => {
      const filteredModels = models.filter(model => 
        model.label.toLowerCase().includes(searchLower) ||
        model.value.toLowerCase().includes(searchLower) ||
        model.description.toLowerCase().includes(searchLower) ||
        provider.toLowerCase().includes(searchLower)
      )
      
      if (filteredModels.length > 0) {
        filtered[provider] = filteredModels
      }
    })
    
    return filtered
  }, [groupedModels, search])

  const getProviderBadgeColor = (provider: string) => {
    switch (provider) {
      case 'claude':
        return 'bg-orange-100 text-orange-800 hover:bg-orange-100'
      case 'gemini':
        return 'bg-blue-100 text-blue-800 hover:bg-blue-100'
      case 'openai':
        return 'bg-green-100 text-green-800 hover:bg-green-100'
      case 'ollama':
        return 'bg-purple-100 text-purple-800 hover:bg-purple-100'
      default:
        return 'bg-gray-100 text-gray-800 hover:bg-gray-100'
    }
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between"
        >
          {selectedModel ? (
            <div className="flex items-center gap-2 truncate">
              <Badge variant="outline" className={cn("text-xs", getProviderBadgeColor(selectedModel.provider))}>
                {selectedModel.provider}
              </Badge>
              <span className="truncate">{selectedModel.label}</span>
            </div>
          ) : (
            placeholder
          )}
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[500px] p-0" align="start">
        <Command>
          <CommandInput 
            placeholder="Search models..." 
            value={search}
            onValueChange={setSearch}
          />
          <CommandList>
            {Object.keys(filteredGroups).length === 0 ? (
              <div className="py-6 text-center text-sm text-muted-foreground">
                No models found.
              </div>
            ) : (
              Object.entries(filteredGroups).map(([provider, models]) => (
                <CommandGroup key={provider} heading={
                  <div className="flex items-center gap-2">
                    <span className="text-xs uppercase text-muted-foreground">{provider}</span>
                    <Badge variant="outline" className="text-xs">
                      {models.length}
                    </Badge>
                  </div>
                }>
                  {models.map((model) => (
                    <CommandItem
                      key={model.value}
                      value={model.value}
                      onSelect={(currentValue) => {
                        onValueChange(model.value)
                        setOpen(false)
                        setSearch('')
                      }}
                      className="py-3"
                    >
                      <Check
                        className={cn(
                          "mr-2 h-4 w-4",
                          value === model.value ? "opacity-100" : "opacity-0"
                        )}
                      />
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{model.label}</span>
                          {model.value.includes(':') && (
                            <code className="text-xs bg-muted px-1 rounded">
                              {model.value.split(':')[1]}
                            </code>
                          )}
                        </div>
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {model.description}
                        </div>
                      </div>
                    </CommandItem>
                  ))}
                </CommandGroup>
              ))
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}