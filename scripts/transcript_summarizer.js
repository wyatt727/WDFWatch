#!/usr/bin/env node
/**
 * transcript_summarizer.js - Generate podcast summary and keywords using configured LLM
 * 
 * This script reads a podcast transcript and overview, then uses the configured LLM
 * to generate a comprehensive summary and extract keywords for social media engagement.
 * 
 * Usage:
 *   node transcript_summarizer.js [--verbose]
 */

import { readFileSync, writeFileSync, renameSync, existsSync } from 'fs';
import { spawnSync } from 'child_process';
import { join } from 'path';
import { createHash } from 'crypto';

// Configuration
const CONFIG = {
  transcriptPath: 'transcripts/latest.txt',
  overviewPath: 'transcripts/podcast_overview.txt',
  summaryPath: 'transcripts/summary.md',
  keywordsPath: 'transcripts/keywords.json',
  model: process.env.WDF_LLM_MODEL_SUMMARIZATION || process.env.WDF_LLM_MODELS__SUMMARIZATION || 'gemini-2.5-pro',
  maxChunkSize: 16000, // characters per chunk
  verbose: process.argv.includes('--verbose'),
  useMock: process.argv.includes('--mock'),
  // Database prompts from environment
  dbPrompt: process.env.WDF_PROMPT_SUMMARIZATION,
  dbOverview: process.env.WDF_CONTEXT_PODCAST_OVERVIEW
};

// Add after CONFIG definition or near top
const HASH_PATH = 'transcripts/summary.hash';

function computeHash(str) {
  return createHash('sha256').update(str).digest('hex');
}

function loadExistingHash() {
  try {
    return readFileSync(HASH_PATH, 'utf8').trim();
  } catch (_) {
    return null;
  }
}

function saveHash(hash) {
  try {
    writeFileSync(HASH_PATH, hash);
  } catch (err) {
    console.warn('Unable to write hash file:', err.message);
  }
}

/**
 * Log message if verbose mode is enabled
 */
function log(...args) {
  if (CONFIG.verbose) {
    console.log('[gemini]', ...args);
  }
}

/**
 * Read the transcript and overview files
 */
function readInputFiles() {
  try {
    // Check if files exist, create them with mock content if not
    if (!existsSync(CONFIG.transcriptPath)) {
      log(`Creating mock transcript file: ${CONFIG.transcriptPath}`);
      writeFileSync(CONFIG.transcriptPath, "This is a mock transcript of the War, Divorce, or Federalism podcast. In this episode, Rick Becker discusses constitutional rights, liberty, and the importance of federalism in modern governance. He talks about how states should have more power to make their own decisions.");
    }
    
    // Use database overview if available, otherwise read from file
    let overview;
    if (CONFIG.dbOverview) {
      overview = CONFIG.dbOverview.replace(/\\n/g, '\n');
      log('Using podcast overview from database');
    } else {
      if (!existsSync(CONFIG.overviewPath)) {
        log(`Creating mock overview file: ${CONFIG.overviewPath}`);
        writeFileSync(CONFIG.overviewPath, "WDF is a podcast about War, Divorce, and Federalism hosted by Rick Becker. It explores political philosophy, constitutional rights, and liberty.");
      }
      overview = readFileSync(CONFIG.overviewPath, 'utf8');
    }
    
    const transcript = readFileSync(CONFIG.transcriptPath, 'utf8');
    
    log(`Read ${transcript.length} chars from ${CONFIG.transcriptPath}`);
    log(`Read ${overview.length} chars from ${CONFIG.overviewPath}`);
    
    return { transcript, overview };
  } catch (err) {
    console.error(`Error reading input files: ${err.message}`);
    process.exit(1);
  }
}

/**
 * Split long text into chunks of manageable size
 */
function splitIntoChunks(text, maxChunkSize) {
  const chunks = [];
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
 * Generate a mock response for testing when gemini-cli is not available
 */
function generateMockResponse(chunk, overview, isFirstChunk, isLastChunk) {
  log(`Using mock response generator (gemini-cli not available)`);
  
  if (isLastChunk) {
    return `
# War, Divorce, and Federalism Podcast Summary

In this episode of the WDF Podcast, Rick Becker discusses the importance of constitutional rights and liberty in the context of federalism. He emphasizes how the founding fathers designed our system of government to distribute power between the federal government and the states, creating a balance that protects individual freedoms.

Key points covered:
- The historical context of federalism in the United States
- How state sovereignty serves as a check on federal power
- Recent Supreme Court decisions affecting the balance of power
- The role of citizens in preserving constitutional rights

### Keywords signaling tweet relevance
- federalism
- constitutional rights
- liberty
- Rick Becker
- state sovereignty
- limited government
- founding fathers
- freedom
- individual rights
- WDF podcast
- federal overreach
- states' rights
- civil liberties
- separation of powers
- governance
`;
  } else {
    return "Mock summary chunk content. This would be part of the podcast summary.";
  }
}

/**
 * Build prompt with variable substitution
 */
function buildPromptFromTemplate(template, variables) {
  let result = template;
  
  // Handle conditional blocks (e.g., {condition ? 'true text' : 'false text'})
  result = result.replace(/{(\w+)\s*\?\s*'([^']*)'\s*:\s*'([^']*)'\}/g, (match, varName, trueText, falseText) => {
    return variables[varName] ? trueText : falseText;
  });
  
  // Handle simple substitutions (e.g., {variable})
  result = result.replace(/{(\w+)}/g, (match, varName) => {
    return variables[varName] !== undefined ? String(variables[varName]) : match;
  });
  
  return result;
}

/**
 * Call Gemini API via gemini-cli to process a chunk
 */
function processChunk(chunk, overview, isFirstChunk, isLastChunk) {
  // Use mock implementation if explicitly set with --mock flag
  if (CONFIG.useMock) {
    return generateMockResponse(chunk, overview, isFirstChunk, isLastChunk);
  }
  
  let prompt;
  
  // Use database prompt if available
  if (CONFIG.dbPrompt) {
    const variables = {
      is_first_chunk: isFirstChunk,
      is_last_chunk: isLastChunk,
      overview: overview,
      chunk: chunk
    };
    prompt = buildPromptFromTemplate(CONFIG.dbPrompt.replace(/\\n/g, '\n'), variables);
    log('Using summarization prompt from database');
  } else {
    // Fallback to hardcoded prompt
    prompt = `
You are an expert social media manager for the "War, Divorce, or Federalism" podcast hosted by Rick Becker.
${isFirstChunk ? `
Your task is to create an EXTREMELY lengthy and comprehensive summary of this podcast episode, touching on all the topics discussed.
The summary should be detailed enough for someone who hasn't listened to understand all key points.
Include how it relates to the podcast as a whole.
DO NOT start with phrases like "Here is the summary" or "In this episode". Start directly with the summary content.
` : `
Continue analyzing this podcast transcript chunk. Add to the summary you've been building.
`}
${isLastChunk ? `
This is the final chunk. Please finalize your summary and then add a section titled "### Keywords signaling tweet relevance" 
with a list of 20 specific keywords or phrases that would indicate a tweet is relevant to this episode, including WDF and Rick Becker.

FORMAT REQUIREMENTS FOR KEYWORDS:
- List each keyword or phrase on its own line with a bullet point (- ) prefix
- Use proper names exactly as they appear
- Include both specific terms and broader concepts
- Make sure each keyword/phrase is truly distinctive to this episode's content

These keywords will be used to find relevant social media posts to engage with.
` : ''}

PODCAST OVERVIEW:
${overview}

TRANSCRIPT CHUNK:
${chunk}
`;
  }

  log(`Calling gemini (chunk ${isFirstChunk ? 'first' : isLastChunk ? 'last' : 'middle'})`);
  
  const result = spawnSync('gemini', ['--model', CONFIG.model, '-p', prompt], { 
    encoding: 'utf8',
    maxBuffer: 10 * 1024 * 1024 // 10MB
  });
  
  if (result.status !== 0) {
    console.error('gemini failed:', result.stderr);
    throw new Error(`gemini exited with code ${result.status}`);
  }
  
  let response = result.stdout.trim();
  
  // Clean up the response by removing introductory text
  if (isFirstChunk) {
    // Remove common introductory phrases
    response = response.replace(/^(Of course\.|Here is|I'll provide|Sure\.|Let me|Here's|Below is).*?\n\n/i, '');
    response = response.replace(/^(This is|The following is|Please find|I've created|I have created).*?\n\n/i, '');
  }
  
  return response;
}

/**
 * Extract keywords from the summary
 */
function extractKeywords(summary) {
  // Look for the keywords section with proper heading
  const keywordsSection = summary.match(/### Keywords signaling tweet relevance\s*\n([\s\S]*?)(\n\s*###|\n\s*$|$)/i);
  
  if (!keywordsSection) {
    console.warn('Could not find keywords section in summary');
    log('Summary content:', summary.slice(-300)); // Log the end of the summary to debug
    
    // Extract potential keywords from the summary as fallback
    const words = summary.match(/\b\w+\b/g) || [];
    const uniqueWords = [...new Set(words)].filter(w => w.length > 4).slice(0, 15);
    return uniqueWords;
  }
  
  const keywordsText = keywordsSection[1].trim();
  log('Found keywords section:', keywordsText);
  
  // Extract bullet point items, preserving multi-word phrases
  const keywordLines = keywordsText.split('\n');
  const keywords = keywordLines
    .map(line => line.trim().replace(/^[•\-*]\s*/, '').replace(/^"(.+)"$/, '$1'))
    .filter(keyword => keyword.length > 0 && !keyword.match(/^(here are|these are|the following|keywords include)/i));
  
  // Log extracted keywords for debugging
  log(`Extracted ${keywords.length} keywords: ${JSON.stringify(keywords)}`);
  
  return keywords;
}

/**
 * Write output files atomically using temp files
 */
function writeOutputFiles(summary, keywords) {
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
    console.error(`Error writing output files: ${err.message}`);
    process.exit(1);
  }
}

/**
 * Main function
 */
async function main() {
  try {
    console.log('🔍 Generating podcast summary and keywords...');
    
    if (CONFIG.useMock) {
      console.log('⚠️  Using mock implementation (explicitly requested with --mock flag)');
    }
    
    // Read input files
    const { transcript, overview } = readInputFiles();
    
    const inputHash = computeHash(transcript + '\n' + overview);
    const existingHash = loadExistingHash();

    if (existingHash === inputHash && existsSync(CONFIG.summaryPath) && existsSync(CONFIG.keywordsPath)) {
      console.log('✅ Transcript unchanged. Reusing existing summary and keywords.');
      return;
    }
    
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
    saveHash(inputHash);
    
  } catch (err) {
    console.error(`❌ Error: ${err.message}`);
    process.exit(1);
  }
}

// Run the main function
main(); 