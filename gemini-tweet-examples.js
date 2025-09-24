#!/usr/bin/env node
/* -----------------------------------------------------------
   gemini-tweet-examples.js
   -----------------------------------------------------------
   Description:
   Generates *N* few-shot tweet examples (default 40) in the
   Gemma 3n format by feeding a long-form summary to the
   Google Gemini CLI.

   USAGE
     # Default — reads transcripts/summary.md, writes few_shot_examples.py
     node gemini-tweet-examples.js

     # Custom paths / counts
     node gemini-tweet-examples.js \
         --summary ./my_summary.md \
         --out ./my_examples.py \
         --count 150

     # Help
     node gemini-tweet-examples.js -h | --help
   ----------------------------------------------------------- */
   import { readFileSync, writeFileSync } from 'fs';
   import { tmpdir }               from 'os';
   import { join }                 from 'path';
   import { execSync }             from 'child_process';
   import { mkdtempSync }          from 'fs';
   
   // -----------------------------
   // Simple CLI argument parsing
   // -----------------------------
   function parseArgs() {
     const args = process.argv.slice(2);
     const opts = {
       summary: 'transcripts/summary.md',
       out: 'few_shot_examples.py',
       count: 500,
       help: false,
     };
   
     for (let i = 0; i < args.length; i++) {
       const arg = args[i];
       switch (arg) {
         case '-s':
         case '--summary':
           opts.summary = args[++i];
           break;
         case '-o':
         case '--out':
           opts.out = args[++i];
           break;
         case '-n':
         case '--count':
         case '--num':
         case '--rows':
           opts.count = parseInt(args[++i], 10);
           break;
         case '-h':
         case '--help':
           opts.help = true;
           break;
         default:
           console.error(`Unknown option: ${arg}`);
           opts.help = true;
           break;
       }
     }
     return opts;
   }
   
   const { summary: SUMMARY_PATH, out: OUT_FILE, count: ROW_COUNT, help } = parseArgs();
   
   if (help) {
     console.log(`See script header for usage.`);
     process.exit(0);
   }
   
   if (!ROW_COUNT || ROW_COUNT <= 0) {
     console.error('⛔  --count must be a positive integer');
     process.exit(1);
   }
   
   // 1. Read the summary --------------------------------------------------------
   let summaryText;
   try {
     summaryText = readFileSync(SUMMARY_PATH, 'utf8');
   } catch (err) {
     console.error(`⛔  Could not read summary file at "${SUMMARY_PATH}":`, err.message);
     process.exit(1);
   }
   
   // 2. Craft the exact-format prompt ------------------------------------------
   const prompt = `
   Read the following episode summary and, WITHOUT ADDING ANY OTHER TEXT,
   return exactly ${ROW_COUNT} tweet examples in the format below.
   
   Requirements:
   • Odd-numbered rows must be unrelated to the summary and labelled "SKIP".
   • Even-numbered rows must be related to the summary and labelled "RELEVANT".
   • Do NOT include any inline comments inside the Python list.
   • Produce exactly ${ROW_COUNT} rows.
   
   ### Few-shot examples in Gemma 3n format (${ROW_COUNT})
   
   \`\`\`python
   # Few-shot examples in Gemma 3n format
   FEW_SHOT_EXAMPLES = [
       ("placeholder", "SKIP"),
   ]
   \`\`\`
   
   Episode summary:
   """
   ${summaryText}
   """`;
   
   // 3. Write prompt to a temp file to avoid shell length limits ---------------
   const tmpDir  = mkdtempSync(join(tmpdir(), 'gemini-'));
   const promptFile = join(tmpDir, 'prompt.txt');
   writeFileSync(promptFile, prompt);
   
   // 4. Call Gemini CLI in non-interactive mode --------------------------------
   const geminiCmd = `gemini --prompt "$(cat ${promptFile})"`;
   let generated;
   try {
     console.log('🪄 Invoking Gemini CLI…');
     generated = execSync(geminiCmd, {
       encoding: 'utf8',
       stdio: ['ignore', 'pipe', 'inherit'], // stream stderr live
       maxBuffer: 10 * 1024 * 1024, // 10 MB
     });
   } catch (err) {
     console.error('⛔  Gemini CLI invocation failed:', err.message);
     process.exit(1);
   }
   
   // 5. Persist result ----------------------------------------------------------
   try {
     writeFileSync(OUT_FILE, generated);
     console.log(`✅ ${ROW_COUNT} examples written to ${OUT_FILE}`);
   } catch (err) {
     console.error('⛔  Failed to write output file:', err.message);
     process.exit(1);
   }