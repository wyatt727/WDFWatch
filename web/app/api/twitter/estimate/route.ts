/**
 * Twitter API Cost Estimation Endpoint
 * 
 * Estimates API call cost before executing a search.
 * POST /api/twitter/estimate - Returns cost estimate for keyword search
 */

import { NextRequest, NextResponse } from 'next/server'
import { exec } from 'child_process'
import { promisify } from 'util'
import path from 'path'

const execAsync = promisify(exec)

interface EstimateRequest {
  keywords: string[] | { keyword: string; weight: number }[]
  targetTweets?: number
}

export async function POST(request: NextRequest) {
  try {
    const body: EstimateRequest = await request.json()
    const { keywords, targetTweets = 100 } = body

    if (!keywords || !Array.isArray(keywords) || keywords.length === 0) {
      return NextResponse.json(
        { error: 'Keywords array is required' },
        { status: 400 }
      )
    }

    // Prepare keywords for Python script
    const keywordsJson = JSON.stringify(keywords)
    
    // Execute Python script to get cost estimate
    const scriptPath = path.join(process.cwd(), '..', 'scripts', 'estimate_api_cost.py')
    
    const { stdout, stderr } = await execAsync(
      `cd ${path.join(process.cwd(), '..')} && python ${scriptPath} '${keywordsJson}' ${targetTweets}`,
      {
        env: {
          ...process.env,
          PYTHONPATH: path.join(process.cwd(), '..', 'src')
        }
      }
    )

    if (stderr) {
      console.error('Cost estimation script error:', stderr)
    }

    // Parse the JSON output
    const estimate = JSON.parse(stdout)

    return NextResponse.json(estimate)

  } catch (error) {
    console.error('Error estimating API cost:', error)
    
    // Return mock estimate for development
    if (process.env.NODE_ENV === 'development') {
      const mockKeywordCount = Array.isArray(body?.keywords) ? body.keywords.length : 30
      const queries = Math.ceil(mockKeywordCount / 25) // 25 keywords per OR query
      const pagesPerQuery = Math.ceil((body?.targetTweets || 100) / 100)
      const totalCalls = queries * pagesPerQuery
      
      return NextResponse.json({
        keywords: mockKeywordCount,
        queries_needed: queries,
        pages_per_query: pagesPerQuery,
        total_api_calls: totalCalls,
        percentage_of_remaining: (totalCalls / 6500) * 100,
        can_afford: totalCalls <= 6500 * 0.9,
        remaining_after: Math.max(0, 6500 - totalCalls),
        optimization: {
          phases: [
            {
              name: 'High Priority',
              keywords: Math.floor(mockKeywordCount * 0.3),
              queries: Math.ceil(mockKeywordCount * 0.3 / 25),
              api_calls: Math.ceil(mockKeywordCount * 0.3 / 25) * pagesPerQuery
            },
            {
              name: 'Medium Priority',
              keywords: Math.floor(mockKeywordCount * 0.5),
              queries: Math.ceil(mockKeywordCount * 0.5 / 25),
              api_calls: Math.ceil(mockKeywordCount * 0.5 / 25) * pagesPerQuery
            },
            {
              name: 'Low Priority',
              keywords: Math.floor(mockKeywordCount * 0.2),
              queries: Math.ceil(mockKeywordCount * 0.2 / 25),
              api_calls: Math.ceil(mockKeywordCount * 0.2 / 25) * pagesPerQuery
            }
          ],
          total_optimized_calls: Math.ceil(totalCalls * 0.6),
          savings_percentage: 40
        },
        recommendations: [
          mockKeywordCount > 50 ? 'Consider reducing keywords to under 50 for efficiency' : null,
          totalCalls > 100 ? 'This search will consume significant quota' : null,
          'High-weight keywords will be prioritized automatically'
        ].filter(Boolean)
      })
    }

    return NextResponse.json(
      { error: 'Failed to estimate API cost' },
      { status: 500 }
    )
  }
}