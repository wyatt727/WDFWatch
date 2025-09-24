/**
 * Twitter API Quota Endpoint
 * 
 * Provides quota statistics from the Python quota_manager.
 * GET /api/twitter/quota - Returns current quota stats
 */

import { NextRequest, NextResponse } from 'next/server'
import { exec } from 'child_process'
import { promisify } from 'util'
import path from 'path'

const execAsync = promisify(exec)

export async function GET(request: NextRequest) {
  try {
    // Execute Python script to get quota stats
    const scriptPath = path.join(process.cwd(), '..', 'scripts', 'get_quota_stats.py')
    
    const { stdout, stderr } = await execAsync(
      `cd ${path.join(process.cwd(), '..')} && python ${scriptPath}`,
      {
        env: {
          ...process.env,
          PYTHONPATH: path.join(process.cwd(), '..', 'src')
        }
      }
    )

    if (stderr) {
      console.error('Quota stats script error:', stderr)
    }

    // Parse the JSON output
    const stats = JSON.parse(stdout)

    // Add health status based on percentage
    let health: 'healthy' | 'warning' | 'critical' = 'healthy'
    if (stats.monthly_percentage >= 90) {
      health = 'critical'
    } else if (stats.monthly_percentage >= 70) {
      health = 'warning'
    }

    return NextResponse.json({
      ...stats,
      health
    })

  } catch (error) {
    console.error('Error fetching quota stats:', error)
    
    // Return mock data for development if script fails
    if (process.env.NODE_ENV === 'development') {
      return NextResponse.json({
        monthly_limit: 10000,
        monthly_usage: 3500,
        monthly_remaining: 6500,
        monthly_percentage: 35,
        daily_usage: 120,
        daily_average: 116.67,
        projected_monthly: 3500,
        days_until_exhausted: 55.71,
        exhaustion_date: new Date(Date.now() + 55.71 * 24 * 60 * 60 * 1000).toISOString(),
        days_remaining_in_month: 20,
        recommended_daily_limit: 325,
        health: 'healthy'
      })
    }

    return NextResponse.json(
      { error: 'Failed to fetch quota statistics' },
      { status: 500 }
    )
  }
}