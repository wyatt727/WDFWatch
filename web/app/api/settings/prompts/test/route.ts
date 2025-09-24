import { NextRequest, NextResponse } from 'next/server'

// POST /api/settings/prompts/test - Test a prompt template with sample data
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { template, variables = [], sampleData = {} } = body

    if (!template) {
      return NextResponse.json(
        { error: 'Missing template' },
        { status: 400 }
      )
    }

    // Simple variable substitution for testing
    let result = template
    const usedData: Record<string, any> = {}

    // Process each variable
    for (const variable of variables) {
      if (sampleData[variable] !== undefined) {
        // Use provided sample data
        usedData[variable] = sampleData[variable]
        
        // Handle conditional syntax: {variable ? 'true' : 'false'}
        const conditionalRegex = new RegExp(`{${variable}\\s*\\?\\s*([^:}]+)\\s*:\\s*([^}]+)}`, 'g')
        result = result.replace(conditionalRegex, (match: string, trueValue: string, falseValue: string) => {
          const value = sampleData[variable]
          return value ? trueValue.replace(/['"]/g, '') : falseValue.replace(/['"]/g, '')
        })
        
        // Handle simple substitution: {variable}
        const simpleRegex = new RegExp(`{${variable}}`, 'g')
        result = result.replace(simpleRegex, String(sampleData[variable]))
      } else {
        // Generate mock data for testing
        const mockValue = generateMockValue(variable)
        usedData[variable] = mockValue
        
        // Handle conditional syntax
        const conditionalRegex = new RegExp(`{${variable}\\s*\\?\\s*([^:}]+)\\s*:\\s*([^}]+)}`, 'g')
        result = result.replace(conditionalRegex, (match: string, trueValue: string, falseValue: string) => {
          return mockValue ? trueValue.replace(/['"]/g, '') : falseValue.replace(/['"]/g, '')
        })
        
        // Handle simple substitution
        const simpleRegex = new RegExp(`{${variable}}`, 'g')
        result = result.replace(simpleRegex, String(mockValue))
      }
    }

    return NextResponse.json({
      result,
      variables,
      usedData
    })
  } catch (error) {
    console.error('Failed to test prompt:', error)
    return NextResponse.json({ error: 'Failed to test prompt' }, { status: 500 })
  }
}

function generateMockValue(variable: string): any {
  // Generate realistic mock data based on variable name
  switch (variable.toLowerCase()) {
    case 'is_first_chunk':
    case 'is_last_chunk':
      return Math.random() > 0.5
    case 'required_examples':
      return 40
    case 'max_length':
      return 200
    case 'overview':
    case 'podcast_overview':
      return 'The War, Divorce, or Federalism podcast explores critical issues of liberty, constitutional governance, and state sovereignty.'
    case 'chunk':
      return 'In this episode, Rick Becker discusses the importance of state sovereignty and how federal overreach threatens individual liberty...'
    case 'summary':
      return 'This episode covers the ongoing debate about federal government authority versus state rights, examining recent Supreme Court cases and their implications for constitutional federalism.'
    case 'topic_summary':
      return 'Discussion about federal government overreach and state sovereignty'
    case 'video_url':
      return 'https://youtu.be/example-episode'
    default:
      return `[mock_${variable}]`
  }
}