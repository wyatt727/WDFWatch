'use client'

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { EyeIcon, EyeOffIcon, SaveIcon, AlertCircle, CheckCircle2 } from 'lucide-react'
import { useToast } from '@/components/ui/use-toast'

interface ApiKeysConfig {
  twitter?: {
    apiKey?: string
    apiKeySet?: boolean
    apiSecret?: string
    apiSecretSet?: boolean
    bearerToken?: string
    bearerTokenSet?: boolean
    accessToken?: string
    accessTokenSet?: boolean
    accessTokenSecret?: string
    accessTokenSecretSet?: boolean
  }
  gemini?: {
    apiKey?: string
    apiKeySet?: boolean
  }
  openai?: {
    apiKey?: string
    apiKeySet?: boolean
  }
}

export function ApiKeysForm() {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({})
  const [formData, setFormData] = useState<ApiKeysConfig>({})

  // Fetch current API keys (masked)
  const { data: apiKeys, isLoading } = useQuery<ApiKeysConfig>({
    queryKey: ['api-keys'],
    queryFn: async () => {
      const response = await fetch('/api/settings/api-keys')
      if (!response.ok) throw new Error('Failed to fetch API keys')
      return response.json()
    },
  })

  // Update form data when query data changes
  useEffect(() => {
    if (apiKeys) {
      setFormData(apiKeys)
    }
  }, [apiKeys])

  // Update API keys mutation
  const updateMutation = useMutation({
    mutationFn: async (data: ApiKeysConfig) => {
      const response = await fetch('/api/settings/api-keys', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (!response.ok) throw new Error('Failed to update API keys')
      return response.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
      toast({
        title: 'Success',
        description: 'API keys updated successfully',
      })
    },
    onError: (error) => {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to update API keys',
        variant: 'destructive',
      })
    },
  })

  const handleInputChange = (service: string, field: string, value: string) => {
    setFormData(prev => ({
      ...prev,
      [service]: {
        ...prev[service as keyof ApiKeysConfig],
        [field]: value,
      },
    }))
  }

  const handleSave = () => {
    updateMutation.mutate(formData)
  }

  const toggleShowKey = (key: string) => {
    setShowKeys(prev => ({ ...prev, [key]: !prev[key] }))
  }

  if (isLoading) {
    return <div>Loading...</div>
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>External API Configuration</CardTitle>
        <CardDescription>
          Enter your API keys below. All keys are encrypted before storage.
          Leave fields empty to keep existing values.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="twitter" className="space-y-4">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="twitter">Twitter/X</TabsTrigger>
            <TabsTrigger value="gemini">Google Gemini</TabsTrigger>
            <TabsTrigger value="openai">OpenAI</TabsTrigger>
          </TabsList>

          <TabsContent value="twitter" className="space-y-4">
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                For Twitter API v2, you need to create an app at{' '}
                <a 
                  href="https://developer.twitter.com/en/portal/dashboard" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="underline"
                >
                  developer.twitter.com
                </a>
              </AlertDescription>
            </Alert>

            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="twitter-api-key">API Key</Label>
                <div className="flex gap-2">
                  <Input
                    id="twitter-api-key"
                    type={showKeys['twitter-api-key'] ? 'text' : 'password'}
                    value={formData.twitter?.apiKey || ''}
                    onChange={(e) => handleInputChange('twitter', 'apiKey', e.target.value)}
                    placeholder={apiKeys?.twitter?.apiKeySet ? 'Enter new key to update' : 'Enter API key'}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() => toggleShowKey('twitter-api-key')}
                  >
                    {showKeys['twitter-api-key'] ? <EyeOffIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
                  </Button>
                </div>
                {apiKeys?.twitter?.apiKeySet && (
                  <p className="text-sm text-muted-foreground flex items-center gap-1">
                    <CheckCircle2 className="h-3 w-3 text-green-500" />
                    Currently set
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="twitter-api-secret">API Secret</Label>
                <div className="flex gap-2">
                  <Input
                    id="twitter-api-secret"
                    type={showKeys['twitter-api-secret'] ? 'text' : 'password'}
                    value={formData.twitter?.apiSecret || ''}
                    onChange={(e) => handleInputChange('twitter', 'apiSecret', e.target.value)}
                    placeholder={apiKeys?.twitter?.apiSecretSet ? 'Enter new secret to update' : 'Enter API secret'}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() => toggleShowKey('twitter-api-secret')}
                  >
                    {showKeys['twitter-api-secret'] ? <EyeOffIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
                  </Button>
                </div>
                {apiKeys?.twitter?.apiSecretSet && (
                  <p className="text-sm text-muted-foreground flex items-center gap-1">
                    <CheckCircle2 className="h-3 w-3 text-green-500" />
                    Currently set
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="twitter-bearer-token">Bearer Token</Label>
                <div className="flex gap-2">
                  <Input
                    id="twitter-bearer-token"
                    type={showKeys['twitter-bearer-token'] ? 'text' : 'password'}
                    value={formData.twitter?.bearerToken || ''}
                    onChange={(e) => handleInputChange('twitter', 'bearerToken', e.target.value)}
                    placeholder={apiKeys?.twitter?.bearerTokenSet ? 'Enter new token to update' : 'Enter bearer token'}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() => toggleShowKey('twitter-bearer-token')}
                  >
                    {showKeys['twitter-bearer-token'] ? <EyeOffIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
                  </Button>
                </div>
                {apiKeys?.twitter?.bearerTokenSet && (
                  <p className="text-sm text-muted-foreground flex items-center gap-1">
                    <CheckCircle2 className="h-3 w-3 text-green-500" />
                    Currently set
                  </p>
                )}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="gemini" className="space-y-4">
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                <div className="space-y-2">
                  <p>
                    Gemini models are accessed via the free{' '}
                    <a 
                      href="https://www.npmjs.com/package/gemini-cli" 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="underline"
                    >
                      gemini-cli npm package
                    </a>
                    , not through an API key.
                  </p>
                  <p className="text-sm">
                    To use Gemini models, ensure gemini-cli is installed:
                    <code className="ml-2 bg-muted px-2 py-1 rounded text-xs">npm install -g gemini-cli</code>
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Note: The free tier has usage limits. Premium access would require an API key (not currently supported).
                  </p>
                </div>
              </AlertDescription>
            </Alert>

            <div className="space-y-4">
              <Card className="bg-muted/50">
                <CardContent className="pt-6">
                  <h4 className="font-medium mb-2">Installation Status</h4>
                  <p className="text-sm text-muted-foreground mb-3">
                    The system will automatically check if gemini-cli is installed when you select a Gemini model.
                  </p>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={async () => {
                      try {
                        const response = await fetch('/api/settings/llm-models/validate', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ model: 'gemini-2.5-pro', provider: 'gemini' })
                        })
                        const result = await response.json()
                        toast({
                          title: result.valid ? 'Gemini CLI Available' : 'Gemini CLI Not Found',
                          description: result.message,
                          variant: result.valid ? 'default' : 'destructive',
                        })
                      } catch (error) {
                        toast({
                          title: 'Error',
                          description: 'Failed to check Gemini CLI status',
                          variant: 'destructive',
                        })
                      }
                    }}
                  >
                    Check Gemini CLI Status
                  </Button>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="openai" className="space-y-4">
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                OpenAI integration coming soon. Get your API key from{' '}
                <a 
                  href="https://platform.openai.com/api-keys" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="underline"
                >
                  OpenAI Platform
                </a>
              </AlertDescription>
            </Alert>

            <div className="space-y-2">
              <Label htmlFor="openai-api-key">API Key</Label>
              <div className="flex gap-2">
                <Input
                  id="openai-api-key"
                  type={showKeys['openai-api-key'] ? 'text' : 'password'}
                  value={formData.openai?.apiKey || ''}
                  onChange={(e) => handleInputChange('openai', 'apiKey', e.target.value)}
                  placeholder={apiKeys?.openai?.apiKeySet ? 'Enter new key to update' : 'Enter API key'}
                  disabled
                />
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={() => toggleShowKey('openai-api-key')}
                  disabled
                >
                  {showKeys['openai-api-key'] ? <EyeOffIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
                </Button>
              </div>
              <p className="text-sm text-muted-foreground">
                OpenAI support is not yet implemented
              </p>
            </div>
          </TabsContent>
        </Tabs>

        <div className="flex justify-end mt-6">
          <Button 
            onClick={handleSave} 
            disabled={updateMutation.isPending}
          >
            <SaveIcon className="h-4 w-4 mr-2" />
            {updateMutation.isPending ? 'Saving...' : 'Save API Keys'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}