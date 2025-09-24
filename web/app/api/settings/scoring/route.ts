import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

const SETTINGS_KEY = 'scoring_config';
const DEFAULT_CONFIG = {
  relevancy_threshold: 0.70,
  score_ranges: {
    high: { min: 0.85, max: 1.00, label: "Highly Relevant" },
    relevant: { min: 0.70, max: 0.84, label: "Relevant" },
    maybe: { min: 0.30, max: 0.69, label: "Maybe Relevant" },
    skip: { min: 0.00, max: 0.29, label: "Not Relevant" }
  },
  priority_threshold: 0.85,  // Tweets above this score get priority processing
  review_threshold: 0.50     // Tweets between review_threshold and relevancy_threshold could be manually reviewed
};

export async function GET() {
  try {
    // Try to get existing config
    const setting = await prisma.setting.findUnique({
      where: { key: SETTINGS_KEY }
    });

    const config = setting ? setting.value : DEFAULT_CONFIG;

    return NextResponse.json(config);
  } catch (error) {
    console.error('Failed to fetch scoring config:', error);
    return NextResponse.json(
      { error: 'Failed to fetch scoring configuration' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const config = await request.json();

    // Validate the configuration
    if (!config.relevancy_threshold || typeof config.relevancy_threshold !== 'number') {
      return NextResponse.json(
        { error: 'Invalid relevancy_threshold' },
        { status: 400 }
      );
    }

    if (config.relevancy_threshold < 0 || config.relevancy_threshold > 1) {
      return NextResponse.json(
        { error: 'relevancy_threshold must be between 0.00 and 1.00' },
        { status: 400 }
      );
    }

    // Validate optional thresholds
    if (config.priority_threshold !== undefined) {
      if (typeof config.priority_threshold !== 'number' || 
          config.priority_threshold < 0 || 
          config.priority_threshold > 1) {
        return NextResponse.json(
          { error: 'priority_threshold must be between 0.00 and 1.00' },
          { status: 400 }
        );
      }
    }

    if (config.review_threshold !== undefined) {
      if (typeof config.review_threshold !== 'number' || 
          config.review_threshold < 0 || 
          config.review_threshold > 1) {
        return NextResponse.json(
          { error: 'review_threshold must be between 0.00 and 1.00' },
          { status: 400 }
        );
      }
    }

    // Ensure logical consistency
    if (config.priority_threshold && config.priority_threshold < config.relevancy_threshold) {
      return NextResponse.json(
        { error: 'priority_threshold must be greater than or equal to relevancy_threshold' },
        { status: 400 }
      );
    }

    if (config.review_threshold && config.review_threshold >= config.relevancy_threshold) {
      return NextResponse.json(
        { error: 'review_threshold must be less than relevancy_threshold' },
        { status: 400 }
      );
    }

    // Update score ranges based on relevancy threshold
    if (config.score_ranges) {
      config.score_ranges.relevant.min = config.relevancy_threshold;
      config.score_ranges.maybe.max = config.relevancy_threshold - 0.01;
    }

    // Save to database
    await prisma.setting.upsert({
      where: { key: SETTINGS_KEY },
      update: { value: config },
      create: { key: SETTINGS_KEY, value: config }
    });

    return NextResponse.json({ 
      message: 'Scoring configuration saved successfully',
      config 
    });
  } catch (error) {
    console.error('Failed to save scoring config:', error);
    return NextResponse.json(
      { error: 'Failed to save scoring configuration' },
      { status: 500 }
    );
  }
}

export async function DELETE() {
  try {
    // Reset to default configuration
    await prisma.setting.upsert({
      where: { key: SETTINGS_KEY },
      update: { value: DEFAULT_CONFIG },
      create: { key: SETTINGS_KEY, value: DEFAULT_CONFIG }
    });

    return NextResponse.json({ 
      message: 'Scoring configuration reset to defaults',
      config: DEFAULT_CONFIG 
    });
  } catch (error) {
    console.error('Failed to reset scoring config:', error);
    return NextResponse.json(
      { error: 'Failed to reset scoring configuration' },
      { status: 500 }
    );
  }
}