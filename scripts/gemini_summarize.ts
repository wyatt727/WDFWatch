#!/usr/bin/env node
/**
 * gemini_summarize.ts - Generate podcast summary and keywords using Gemini API
 * 
 * This script reads a podcast transcript and overview, then uses the Gemini API
 * to generate a comprehensive summary and extract keywords for social media engagement.
 * 
 * Usage:
 *   ts-node gemini_summarize.ts [--verbose]
 *   or
 *   npm run summarize [-- --verbose]
 */

import { readFileSync, writeFileSync, renameSync } from 'fs';
import { spawnSync, SpawnSyncReturns } from 'child_process';
import { join } from 'path';
import { createHash } from 'crypto';

// Configuration interface
interface Config {
  transcriptPath: string;
  overviewPath: string;
  summaryPath: string;
  keywordsPath: string;
  model: string;
  maxChunkSize: number;
  verbose: boolean;
}

// Input files interface
interface InputFiles {
  transcript: string;
  overview: string;
}

// Configuration
const CONFIG: Config = {
  transcriptPath: 'transcripts/latest.txt',
  overviewPath: 'transcripts/podcast_overview.txt',
  summaryPath: 'transcripts/summary.md',
  keywordsPath: 'transcripts/keywords.json',
  model: 'gemini-2.5-pro',
  maxChunkSize: 16000, // characters per chunk
  verbose: process.argv.includes('--verbose')
};

/**
 * Log message if verbose mode is enabled
 */
function log(...args: any[]): void {
  if (CONFIG.verbose) {
    console.log('[gemini]', ...args);
  }
}

/**
 * Read the transcript and overview files
 */
function readInputFiles(): InputFiles {
  try {
    const transcript = readFileSync(CONFIG.transcriptPath, 'utf8');
    const overview = readFileSync(CONFIG.overviewPath, 'utf8');
    
    log(`Read ${transcript.length} chars from ${CONFIG.transcriptPath}`);
    log(`Read ${overview.length} chars from ${CONFIG.overviewPath}`);
    
    return { transcript, overview };
  } catch (err) {
    console.error(`Error reading input files: ${(err as Error).message}`);
    process.exit(1);
  }
}

/**
 * Split long text into chunks of manageable size
 */
function splitIntoChunks(text: string, maxChunkSize: number): string[] {
  const chunks: string[] = [];
  let currentChunk = '';
  
  // Split by paragraphs to avoid cutting in the middle of sentences
  const paragraphs = text.split(/\n\s*\n/);
  
  for (const paragraph of paragraphs) {
    if (currentChunk.length + paragraph.length + 2 <= maxChunkSize) {
      currentChunk += (currentChunk ? '\n\n' : '') + paragraph;
    } else {
      if (currentChunk) {
        chunks.push(currentChunk);
      }
      currentChunk = paragraph;
    }
  }
  
  if (currentChunk) {
    chunks.push(currentChunk);
  }
  
  log(`Split transcript into ${chunks.length} chunks`);
  return chunks;
}

/**
 * Call Gemini API via gemini-cli to process a chunk
 */
function processChunk(chunk: string, overview: string, isFirstChunk: boolean, isLastChunk: boolean): string {
  const prompt = `
You are an expert social media manager for the "War, Divorce, or Federalism" podcast hosted by Rick Becker.
${isFirstChunk ? `
Your task is to create a comprehensive summary of this podcast episode.
The summary should be detailed enough for someone who hasn't listened to understand all key points.
` : `
Continue analyzing this podcast transcript chunk. Add to the summary you've been building.
`}
${isLastChunk ? `
This is the final chunk. Please finalize your summary and then add a section titled "### Keywords signaling tweet relevance" 
with a list of 10-15 specific keywords or phrases that would indicate a tweet is relevant to this episode.
These keywords will be used to find relevant social media posts to engage with.
` : ''}

PODCAST OVERVIEW:
${overview}

TRANSCRIPT CHUNK:
${chunk}
`;

  log(`Calling gemini-cli (chunk ${isFirstChunk ? 'first' : isLastChunk ? 'last' : 'middle'})`);
  
  const result: SpawnSyncReturns<string> = spawnSync('gemini-cli', ['--model', CONFIG.model, '--stdin'], { 
    input: prompt, 
    encoding: 'utf8',
    maxBuffer: 10 * 1024 * 1024 // 10MB
  });
  
  if (result.status !== 0) {
    console.error('gemini-cli failed:', result.stderr);
    throw new Error(`gemini-cli exited with code ${result.status}`);
  }
  
  return result.stdout.trim();
}

/**
 * Extract keywords from the summary
 */
function extractKeywords(summary: string): string[] {
  const keywordsMatch = summary.match(/### Keywords signaling tweet relevance\s*\n([\s\S]*?)(\n\s*---|\Z)/i);
  
  if (!keywordsMatch) {
    console.warn('Could not find keywords section in summary');
    // Extract potential keywords from the summary as fallback
    const words = summary.match(/\b\w+\b/g) || [];
    const uniqueWords = [...new Set(words)].filter(w => w.length > 4).slice(0, 15);
    return uniqueWords;
  }
  
  const keywordsText = keywordsMatch[1].trim();
  const keywords = keywordsText
    .split(/[\n,]/)
    .map(k => k.trim().replace(/^[•\-*]\s*/, ''))
    .filter(k => k.length > 0);
  
  return keywords;
}

/**
 * Write output files atomically using temp files
 */
function writeOutputFiles(summary: string, keywords: string[]): void {
  try {
    // Write to temp files first
    const summaryTemp = `${CONFIG.summaryPath}.tmp`;
    const keywordsTemp = `${CONFIG.keywordsPath}.tmp`;
    
    writeFileSync(summaryTemp, summary);
    writeFileSync(keywordsTemp, JSON.stringify(keywords, null, 2));
    
    // Rename for atomic write
    renameSync(summaryTemp, CONFIG.summaryPath);
    renameSync(keywordsTemp, CONFIG.keywordsPath);
    
    log(`Wrote ${summary.length} chars to ${CONFIG.summaryPath}`);
    log(`Wrote ${keywords.length} keywords to ${CONFIG.keywordsPath}`);
    
    console.log(`✅ Summary and keywords generated successfully`);
  } catch (err) {
    console.error(`Error writing output files: ${(err as Error).message}`);
    process.exit(1);
  }
}

/**
 * Main function
 */
async function main(): Promise<void> {
  try {
    console.log('🔍 Generating podcast summary and keywords...');
    
    // Read input files
    const { transcript, overview } = readInputFiles();
    
    // Split transcript into chunks if needed
    const chunks = splitIntoChunks(transcript, CONFIG.maxChunkSize);
    
    // Process each chunk
    let fullSummary = '';
    for (let i = 0; i < chunks.length; i++) {
      const isFirstChunk = i === 0;
      const isLastChunk = i === chunks.length - 1;
      
      const chunkResult = processChunk(
        chunks[i], 
        overview, 
        isFirstChunk, 
        isLastChunk
      );
      
      fullSummary += (fullSummary && !isFirstChunk ? '\n\n' : '') + chunkResult;
    }
    
    // Extract keywords
    const keywords = extractKeywords(fullSummary);
    
    // Write output files
    writeOutputFiles(fullSummary, keywords);
    
  } catch (err) {
    console.error(`❌ Error: ${(err as Error).message}`);
    process.exit(1);
  }
}

// Run the main function
main(); 