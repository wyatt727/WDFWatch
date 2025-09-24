import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function GET() {
  try {
    // Get current date and calculate period
    const now = new Date();
    const periodStart = new Date(now.getFullYear(), now.getMonth(), 1);
    const periodEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0);

    // Find or create quota usage for current period
    let quotaUsage = await prisma.quotaUsage.findUnique({
      where: {
        periodStart_periodEnd: {
          periodStart,
          periodEnd,
        },
      },
    });

    if (!quotaUsage) {
      quotaUsage = await prisma.quotaUsage.create({
        data: {
          periodStart,
          periodEnd,
          totalAllowed: 10000,
          used: 0,
          sourceBreakdown: {},
          dailyUsage: {},
        },
      });
    }

    const remaining = quotaUsage.totalAllowed - quotaUsage.used;
    const percentageUsed = (quotaUsage.used / quotaUsage.totalAllowed) * 100;

    return NextResponse.json({
      quota: {
        total: quotaUsage.totalAllowed,
        used: quotaUsage.used,
        remaining,
        percentageUsed,
        periodStart: quotaUsage.periodStart.toISOString(),
        periodEnd: quotaUsage.periodEnd.toISOString(),
        sourceBreakdown: quotaUsage.sourceBreakdown || {},
        dailyUsage: quotaUsage.dailyUsage || {},
      },
    });
  } catch (error) {
    console.error("Failed to fetch quota:", error);
    return NextResponse.json(
      { error: "Failed to fetch quota information" },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { used, source = "unknown" } = body;

    if (typeof used !== "number" || used < 0) {
      return NextResponse.json(
        { error: "Invalid usage value" },
        { status: 400 }
      );
    }

    const now = new Date();
    const periodStart = new Date(now.getFullYear(), now.getMonth(), 1);
    const periodEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    const dateKey = now.toISOString().split("T")[0];

    // Find or create quota usage for current period
    let quotaUsage = await prisma.quotaUsage.findUnique({
      where: {
        periodStart_periodEnd: {
          periodStart,
          periodEnd,
        },
      },
    });

    if (!quotaUsage) {
      quotaUsage = await prisma.quotaUsage.create({
        data: {
          periodStart,
          periodEnd,
          totalAllowed: 10000,
          used: 0,
          sourceBreakdown: {},
          dailyUsage: {},
        },
      });
    }

    // Update source breakdown
    const sourceBreakdown = (quotaUsage.sourceBreakdown as any) || {};
    sourceBreakdown[source] = (sourceBreakdown[source] || 0) + used;

    // Update daily usage
    const dailyUsage = (quotaUsage.dailyUsage as any) || {};
    dailyUsage[dateKey] = (dailyUsage[dateKey] || 0) + used;

    // Update quota usage
    const updated = await prisma.quotaUsage.update({
      where: {
        id: quotaUsage.id,
      },
      data: {
        used: quotaUsage.used + used,
        sourceBreakdown,
        dailyUsage,
      },
    });

    const remaining = updated.totalAllowed - updated.used;
    const percentageUsed = (updated.used / updated.totalAllowed) * 100;

    return NextResponse.json({
      quota: {
        total: updated.totalAllowed,
        used: updated.used,
        remaining,
        percentageUsed,
        periodStart: updated.periodStart.toISOString(),
        periodEnd: updated.periodEnd.toISOString(),
        sourceBreakdown: updated.sourceBreakdown,
        dailyUsage: updated.dailyUsage,
      },
    });
  } catch (error) {
    console.error("Failed to update quota:", error);
    return NextResponse.json(
      { error: "Failed to update quota" },
      { status: 500 }
    );
  }
}