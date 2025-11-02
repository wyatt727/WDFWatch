# Universal Dual-Workflow Agent System

**Version:** 6.0
**Last Updated:** 2025-01-XX
**Agent Systems:**
- **Bug-Fixing Workflow**: 3-4 agents (diagnostic → planning → fixer → [optional] verifier)
- **Feature-Building Workflow**: 3-4 agents (ideator → assigner → engineers → [optional] verifier)
- **Optional Agent**: verifier-agent (works with both workflows - validates code quality, runs tests, fixes common errors)

This document explains both agent workflows for any software project, regardless of language or architecture.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [When to Use Which Workflow](#when-to-use-which-workflow)
3. [Standalone Agent Usage](#standalone-agent-usage)
4. [Bug-Fixing Workflow](#bug-fixing-workflow)
5. [Feature-Building Workflow](#feature-building-workflow)
6. [File Structure](#file-structure)
7. [Best Practices](#best-practices)

---

## System Overview

### 🚀 MAXIMUM SPEED = MAXIMUM PARALLELIZATION

**CRITICAL PRINCIPLE:** **ALWAYS spawn as many fixers/engineers as possible!** 

- **Bug-Fixing:** Multiple fixes = spawn multiple fixers simultaneously (up to 10)
- **Feature-Building:** Multiple files = spawn multiple engineers simultaneously (up to 10)
- **Never wait for one agent to finish before spawning the next!**
- **10 files = 10x faster with parallel agents!**

### Two Distinct Workflows + Optional Verification Agent

This system uses **two specialized agent workflows** optimized for different tasks, plus an optional verification agent:

#### 1. Bug-Fixing Workflow (3-4 agents)
**Purpose:** Diagnose, plan, and fix bugs systematically

```
Bug Found → diagnostic-agent → planning-agent → fixer-agent → [optional] verifier-agent → Fixed!
```

**When to use:** Bugs, crashes, test failures, unexpected behavior

#### 2. Feature-Building Workflow (3-4 agents)
**Purpose:** Design, distribute, and implement new features in parallel

```
Feature Request → ideator-agent → assigner-agent → engineer-agent × N → [optional] verifier-agent → Feature Complete!
```

**When to use:** New features, enhancements, adding functionality

#### 3. Optional Agent: verifier-agent
**Purpose:** Validates code quality, runs tests, fixes common errors (works with both workflows)

**Used by:**
- Bug-Fixing: Optional (validates fixes, runs tests, checks for common errors)
- Feature-Building: Optional (validates implementation, runs tests, fixes syntax/import errors)

**When to use:**
- Projects with automated tests (runs test suite)
- Projects with linters (runs linting and fixes issues)
- Projects with build systems (verifies builds succeed)
- When you want automated quality checks

**What it does:**
- Runs test suites (if available)
- Executes linters (if configured)
- Attempts builds (if build system exists)
- Fixes common errors (missing imports, syntax errors, type mismatches)
- Reports validation results

**Key Difference:**
- **Bug-Fixing**: Mostly sequential (diagnosis → planning), but **MAXIMUM PARALLELIZATION** for fixers (multiple fixes = multiple fixers simultaneously!)
- **Feature-Building**: Fully parallel workflow, maximum speed (10 files = 10 engineers simultaneously!), optional verification at end

**CRITICAL PRINCIPLE:** **ALWAYS spawn as many fixers/engineers as possible!** Don't wait for one to finish before starting the next. Maximum speed = maximum parallelization!

---

## When to Use Which Workflow

### Use Bug-Fixing Workflow When:

✅ **Fixing problems:**
- App crashes
- Tests fail
- Features broken
- Unexpected behavior
- Performance issues
- State corruption

✅ **Need systematic diagnosis:**
- Don't know root cause
- Complex debugging needed
- Multiple related bugs
- Want audit trail of diagnosis

✅ **Sequential is appropriate:**
- Must understand problem before fixing
- Fixes interdependent
- Deploy all together

### Use Feature-Building Workflow When:

✅ **Adding new functionality:**
- New features or modules
- API endpoints
- UI components
- Configuration systems
- Service integrations
- Database schemas

✅ **Maximum speed needed:**
- Multiple files to create/modify
- Files independent (can work in parallel)
- 10 files = 10x faster with parallel engineers

✅ **Have clear requirements:**
- Know what to build (not debugging)
- Can specify interfaces upfront
- Files don't conflict

### Quick Decision Tree

```
Is it broken or new?
├─ Broken → Bug-Fixing Workflow
│   └─ diagnostic → planning → fixer → [optional] verifier
│
└─ New → Feature-Building Workflow
    └─ ideator → assigner → engineers (parallel!) → [optional] verifier
```

---

## Standalone Agent Usage

**All agents can work independently without requiring full workflows!** Use standalone agents when you need quick, focused tasks without the overhead of the complete workflow system.

### When to Use Standalone Agents

✅ **Use standalone agents when:**
- You know exactly what needs to be done (no investigation needed)
- Quick fixes or simple tasks
- Single-file changes
- You want immediate results without planning overhead
- Debugging a specific issue you understand
- Adding a simple feature or utility function

✅ **Use full workflows when:**
- Complex bugs needing systematic diagnosis
- Multi-file features requiring coordination
- You need audit trails and documentation
- Multiple related issues to fix together
- Team collaboration (workflow files serve as documentation)

### Standalone Usage Patterns

#### 1. diagnostic-agent (Standalone)

**Use when:** You want to investigate a bug but don't need a full fix plan yet.

**Example:**
```
@diagnostic-agent "The pipeline fails when classifying tweets - AttributeError: 'NoneType' object has no attribute 'score'"

What it does:
- Investigates tweet classification functionality systematically
- Finds root cause (e.g., None check missing before accessing tweet.score)
- Writes findings to issue-tracker.md
- Reports: "✅ Root cause identified: Missing None check in classify.py before accessing tweet.score. See issue-tracker.md for details."
```

**Output:** Creates or updates `.agent-results/issue-tracker.md` with findings

**No prerequisites:** Works directly from bug description

---

#### 2. planning-agent (Standalone)

**Use when:** You know the issue but want a detailed implementation plan before fixing.

**Example:**
```
@planning-agent "Fix the pipeline crash - AttributeError when tweet score is None"

What it does:
- Investigates the codebase to understand the problem
- Creates comprehensive fix plan for claude-pipeline/stages/classify.py
- Writes plan to fix-plans.md
- Reports: "✅ Fix plan created. See fix-plans.md for detailed implementation steps."
```

**Output:** Creates or updates `.agent-results/fix-plans.md` with implementation plan

**Can work from:**
- Direct issue description (standalone)
- issue-tracker.md entry (if diagnostic-agent ran first)
- User's verbal description

---

#### 3. fixer-agent (Standalone)

**Use when:** You know exactly what needs to be fixed and want immediate implementation.

**Example:**
```
@fixer-agent "Add None check before accessing tweet.score in classify_tweet function"

What it does:
- Finds the relevant code location in claude-pipeline/stages/classify.py
- Implements the fix directly
- Tests the change
- Reports: "✅ Fix implemented. Added None check at classify.py:167. Tests passing."
```

**Output:** Modified code files

**Can work from:**
- Direct fix description (standalone)
- fix-plans.md entry (if planning-agent ran first)
- User's verbal instruction

**Most common standalone usage:** Quick fixes, simple bugs, single-file changes

---

#### 4. ideator-agent (Standalone)

**Use when:** You want to design a feature architecture before building it.

**Example:**
```
@ideator-agent "Design a new pipeline stage for tweet sentiment analysis"

What it does:
- Investigates codebase for existing pipeline stage patterns
- Designs comprehensive feature architecture following WDFWatch patterns
- Specifies all interfaces/APIs upfront (FastAPI routes, service layer, Claude integration)
- Writes detailed plan to build-plans.md
- Reports: "✅ Feature plan created. See build-plans.md for complete architecture."
```

**Output:** Creates or updates `.agent-results/build-plans.md` with feature plan

**No prerequisites:** Works directly from feature description

---

#### 5. assigner-agent (Standalone)

**Use when:** You have a build plan and want to distribute work to engineers.

**Example:**
```
@assigner-agent "Create engineering assignments from build-plans.md"

What it does:
- Reads build-plans.md
- Assigns files to engineers (optimizes for parallelization)
- Creates assignments.md
- Reports: "✅ Assignments created. 5 engineers can start immediately!"
```

**Output:** Creates or updates `.agent-results/assignments.md` with engineer assignments

**Requires:** build-plans.md (from ideator-agent)

---

#### 6. engineer-agent (Standalone)

**Use when:** You know what file to build and want immediate implementation.

**Example:**
```
@engineer-agent ENGINEER_ID=1 "Implement SentimentService.py as specified in assignments.md"

What it does:
- Reads assigned files from assignments.md
- Checks dependencies (usually none!)
- Implements the file(s) following WDFWatch patterns
- Updates engineering-progress.md
- Reports: "✅ SentimentService.py implemented. Status: COMPLETE ✓"
```

**Output:** Created/modified files + progress update

**Can work from:**
- assignments.md entry (workflow integration)
- Direct file specification (standalone)
- User's verbal instruction

**Most common standalone usage:** Building a specific file when you know the requirements

---

#### 7. verifier-agent (Standalone)

**Use when:** You want to validate code quality, run tests, or fix linting issues.

**Example:**
```
@verifier-agent "Run tests and linting, fix any issues found"

What it does:
- Detects available validation tools (pytest for Python, ruff for linting, npm test for Next.js)
- Runs test suites (backend/api and claude-pipeline)
- Executes linters (ruff check, eslint)
- Fixes common errors intelligently (missing imports, type mismatches)
- Reports: "✅ All tests passing. Fixed 2 linting issues. Code validated."
```

**Output:** Validation report + any fixes applied

**No prerequisites:** Works directly on current codebase state

**Perfect for:** Quick quality checks, pre-commit validation, fixing common errors

---

### Standalone vs Workflow Comparison

| Scenario | Standalone Agent | Full Workflow |
|----------|-----------------|---------------|
| **Quick bug fix** (single file) | ✅ fixer-agent | ❌ Overkill |
| **Simple feature** (one file) | ✅ engineer-agent | ❌ Overkill |
| **Bug investigation** | ✅ diagnostic-agent | ⚠️ Optional |
| **Complex bug** (multiple files) | ❌ Not ideal | ✅ Full workflow |
| **Multi-file feature** | ❌ Not ideal | ✅ Full workflow |
| **Need audit trail** | ❌ Limited | ✅ Full workflow |
| **Quick validation** | ✅ verifier-agent | ❌ Overkill |
| **Team collaboration** | ❌ Limited | ✅ Full workflow |

### Hybrid Approaches

You can mix standalone and workflow approaches:

**Example 1: Quick diagnosis, then fix**
```
1. @diagnostic-agent "Investigate login crash" → Creates issue-tracker.md
2. @fixer-agent "Fix the issue in issue-tracker.md" → Implements fix directly
```

**Example 2: Plan, then standalone fix**
```
1. @planning-agent "Plan fix for AttributeError" → Creates fix-plans.md
2. @fixer-agent "Implement fix-plans.md" → Implements from plan
```

**Example 3: Design, then build specific files**
```
1. @ideator-agent "Design user auth system" → Creates build-plans.md
2. @engineer-agent "Build UserService.py from build-plans.md" → Implements one file
```

### Best Practices for Standalone Usage

✅ **Do:**
- Use standalone agents for quick, focused tasks
- Specify clear, actionable instructions
- Use standalone for single-file changes
- Mix standalone agents with workflows when appropriate

❌ **Don't:**
- Use standalone agents for complex multi-file features (use full workflow)
- Skip planning for complex bugs (use diagnostic → planning → fixer)
- Use standalone when you need full audit trails (use workflows)

### Standalone Agent Examples

**Quick Fix:**
```
User: "@fixer-agent Add error handling to tweet classification - return None if tweet is invalid"

fixer-agent:
- Finds tweet classification function in claude-pipeline/stages/classify.py
- Adds error handling
- Tests the change
- Done in 5 minutes!
```

**Quick Validation:**
```
User: "@verifier-agent Run tests and fix any issues"

verifier-agent:
- Runs pytest for backend/api and claude-pipeline
- Fixes missing import in backend/api/app/services/pipeline.py
- Runs ruff check
- All checks passing!
```

**Quick Feature Design:**
```
User: "@ideator-agent Design an email notification system for draft approvals"

ideator-agent:
- Investigates codebase (backend/api, web components)
- Designs complete architecture following FastAPI/Next.js patterns
- Specifies all interfaces (FastAPI routes, service layer, email templates)
- Creates build-plans.md
- Ready for implementation!
```

---


### Overview

3-4 agent workflow for systematic bug diagnosis and fixing with **MAXIMUM PARALLELIZATION** for fixers.

```
┌──────────────────┐
│ diagnostic-agent │  Finds root causes
│   (Analysis)     │  Writes: issue-tracker.md
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ planning-agent   │  Creates fix plans
│   (Design)       │  Writes: fix-plans.md
│                  │  (May create multiple fixes!)
└────────┬─────────┘
         │
         ▼
┌────────────────────────────────────────┐
│  fixer-agent × N (PARALLEL!)          │
│  ALWAYS spawn maximum!                 │
│  ├─ Fixer-1: FileA.py                  │
│  ├─ Fixer-2: FileB.py                  │
│  ├─ Fixer-3: FileC.py                  │
│  └─ Fixer-N: FileN.py                  │
│  All work simultaneously!             │
└────────┬───────────────────────────────┘
         │
         ▼
┌──────────────────┐
│ verifier-agent   │  Validates & tests
│   (Optional)      │  Runs tests, fixes errors
└──────────────────┘
```

### The Agents (3-4)

#### 1. diagnostic-agent
**Role:** Root cause analysis

**What it does:**
- Investigates bugs systematically
- Identifies WHY (not just WHAT)
- Uses sequential-thinking for complex bugs
- Checks server-memory for known issues

**Output:** Issues in `.agent-results/issue-tracker.md`

**Parallel:** ✅ Yes - Multiple can run simultaneously

---

#### 2. planning-agent
**Role:** Solution planning

**What it does:**
- Reads diagnosed issues
- Designs comprehensive fix strategies
- Creates step-by-step implementation plans
- Identifies risks and dependencies

**Output:** Plans in `.agent-results/fix-plans.md`

**Parallel:** ✅ Yes - Multiple can plan different issues

---

#### 3. fixer-agent
**Role:** Implementation

**What it does:**
- Reads plans from fix-plans.md
- Implements fixes step-by-step
- Uses Serena for precise code changes
- Reports progress

**Output:** Modified code files

**Parallel:** ✅ YES - Multiple fixers work simultaneously when fixing different files (up to 10 max)

**CRITICAL:** **ALWAYS spawn as many fixers as possible!** If fix-plans.md contains multiple fixes for different files, spawn one fixer per file/plan. Maximum speed = maximum parallelization!

---

#### 4. verifier-agent (Optional)
**Role:** Code quality validation and testing

**What it does:**
- Runs test suites (if available)
- Executes linters (if configured)
- Attempts builds (if build system exists)
- Fixes common errors (missing imports, syntax errors, type mismatches)
- Reports validation results

**When to use:**
- Projects with automated tests
- Projects with linters/formatters
- When you want quality assurance
- Can be skipped for simple fixes

**Output:** Validation report + any fixes applied

**Parallel:** ❌ No - Only 1, runs after ALL fixers complete (if used)

### Bug-Fixing Workflow Steps

1. **User reports bug** → Spawn diagnostic-agent
2. **diagnostic-agent investigates** → Writes to issue-tracker.md
3. **Spawn planning-agent** → Reads issue, creates plan (may create multiple fixes for different files)
4. **Spawn MULTIPLE fixer-agents IN PARALLEL** → Each reads its assigned plan, implements fix
   - **KEY:** If planning-agent created fixes for FileA, FileB, FileC → spawn 3 fixers simultaneously!
   - **ALWAYS spawn as many fixers as possible** (up to 10 max) - one per file/plan
   - All fixers work simultaneously on different files
5. **Wait for all fixers to complete** → (Optional) spawn verifier-agent
6. **verifier-agent validates** → Runs tests, fixes errors, reports → Done!

**Speed Maximization:** Multiple bugs/fixes = spawn multiple fixers in parallel! Don't wait for one fixer to finish before starting the next.

---

## Feature-Building Workflow

### Overview

3-4 agent parallel workflow for maximum-speed feature development + optional verifier-agent.

```
┌──────────────────┐
│  ideator-agent   │  Designs feature architecture
│   (Planning)     │  Specifies interfaces/APIs
│                  │  Writes: build-plans.md
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ assigner-agent   │  Distributes files to engineers
│ (Distribution)   │  Assigns: Engineer-N → FileX.ext
│                  │  Writes: assignments.md
└────────┬─────────┘
         │
         ▼
┌────────────────────────────────────────┐
│  engineer-agent × N (PARALLEL!)        │
│  All work simultaneously               │
│  ├─ Engineer-1: FileA.ext               │
│  ├─ Engineer-2: FileB.ext               │
│  ├─ Engineer-3: FileC.ext               │
│  └─ Engineer-N: FileN.ext               │
│  Updates: engineering-progress.md      │
└────────┬───────────────────────────────┘
         │
         ▼
┌──────────────────┐
│ verifier-agent   │  Validates & tests
│   (Optional)      │  Runs tests, fixes errors
└────────┬─────────┘
         │
         ▼
    Feature Complete!
```

### The Agents (3-4)

#### 1. ideator-agent (Planning)

**Role:** Strategic feature architect

**What it does:**
- Investigates codebase with Serena
- Searches server-memory for similar features
- Designs **EXHAUSTIVELY COMPREHENSIVE** file-level implementation plan
- **CRITICAL:** Specifies exact interfaces/APIs upfront (package, classes, function signatures)
- **EXPLAINS EVERYTHING:** Every file, every function, every change, every integration point
- **ACHIEVES USER'S OBJECTIVE IN ITS ENTIRETY** - The complete feature from A to Z
- Identifies true dependencies (rare - only for implementation logic)
- Uses sequential-thinking for architectural decisions

**Key Principles:**
- **Be EXHAUSTIVELY comprehensive** - Include EVERYTHING that needs to happen
- **Don't worry about role distribution** - That's assigner-agent's job
- **Specify interfaces so engineers can work in parallel without blocking**
- **Leave nothing out** - The plan should be complete and thorough

**Example Output:**
```markdown
### File Plan

#### File 1: sentiment.py
Location: claude-pipeline/stages/sentiment.py
Module: claude_pipeline.stages.sentiment
API:
```python
def analyze_sentiment(
    episode_id: str,
    tweets_file: Path,
    output_file: Path
) -> List[Dict[str, Any]]:
    """Analyzes sentiment for tweets in batch."""
    pass
```
Dependencies: NONE - create immediately

#### File 2: sentiment.py (route)
Location: backend/api/app/routes/sentiment.py
Will import: from app.services.sentiment_service import SentimentService
API:
```python
@router.post("/episodes/{episode_id}/sentiment/analyze")
async def analyze_sentiment(
    episode_id: str,
    request: SentimentAnalyzeRequest
) -> SentimentAnalyzeResponse:
    """FastAPI endpoint for sentiment analysis."""
    pass
```
Dependencies: NONE - interface specified, work in parallel!
```

**Output:** **EXHAUSTIVELY COMPREHENSIVE** plan in `.agent-results/build-plans.md`

**Focus:** Explain EVERYTHING that needs to happen - every file, every interface, every function signature, every change, every integration. The plan should achieve the user's objective in its entirety. Don't worry about splitting work into roles - that's assigner-agent's job!

**Tools:** Read, Serena, Context7, Server-Memory, Sequential-Thinking

**Parallel:** Only 1 per feature (planning takes time, ~15-30 min for thorough planning)

---

#### 2. assigner-agent (Distribution)

**Role:** File distribution specialist

**What it does:**
- Reads build-plans.md
- Assigns files to engineers (1 file = 1 engineer, usually)
- Notes rare dependencies if needed
- Optimizes for maximum parallelization
- Defaults to ZERO dependencies (ideator specified interfaces!)

**Key Principle:** 90%+ assignments should have NO dependencies - all start immediately!

**Example Output:**
```markdown
### Engineer-1
Assigned Files: claude-pipeline/stages/sentiment.py
Dependencies: NONE - START IMMEDIATELY
Estimated: 30 min

### Engineer-2
Assigned Files: backend/api/app/routes/sentiment.py
Dependencies: NONE - START IMMEDIATELY (interface specified)
Estimated: 25 min

### Engineer-3
Assigned Files: backend/api/app/services/sentiment_service.py
Dependencies: NONE - START IMMEDIATELY (interface specified)
Estimated: 20 min

Result: All 3 engineers work simultaneously!
Sequential time: 75 min
Parallel time: 30 min (limited by slowest)
Speedup: 2.5x ✅
```

**Output:** Assignments in `.agent-results/assignments.md`

**Tools:** Read, Serena, Sequential-Thinking

**Parallel:** Only 1 per feature (fast, ~5 min)

---

#### 3. engineer-agent (Implementation)

**Role:** File implementation specialist

**Spawned:** 2-10 times in parallel (one per file/engineer)

**What it does:**
- Parses ENGINEER_ID from invocation (e.g., "ENGINEER_ID=2")
- Reads assigned files from assignments.md
- Checks dependencies (usually none!)
- If blocked: waits 60s, rechecks (rare)
- If ready: implements files using Serena for precision
- Updates engineering-progress.md when complete

**Simple Workflow:**
```
1. Check: Am I blocked? (Usually no!)
2. If blocked: wait 60s, recheck
3. If ready: implement my file(s)
4. Mark complete
5. Done!
```

**Example Invocation:**
```
Main: "@engineer-agent ENGINEER_ID=1 - Implement your assigned files"
Main: "@engineer-agent ENGINEER_ID=2 - Implement your assigned files"
Main: "@engineer-agent ENGINEER_ID=3 - Implement your assigned files"

All 3 spawn simultaneously, work in parallel!
```

**Output:** Created/modified files + progress in `engineering-progress.md`

**Tools:** Read, Write, Edit, Serena, Bash

**Parallel:** ✅ YES - 2-10 engineers work simultaneously!

---

#### 4. verifier-agent (Optional - Validation & Testing)

**Role:** Code quality validation and testing specialist

**Spawned:** Once after ALL engineer-agents complete (optional)

**What it does:**
- Reads build-plans.md to understand feature architecture
- Reads engineering-progress.md to see what was implemented
- Runs test suites (if available: pytest, jest, cargo test, etc.)
- Executes linters (if configured: pylint, eslint, clippy, etc.)
- Attempts builds (if build system exists: npm build, cargo build, etc.)
- **Fixes common errors intelligently** using context from recent changes
- Reports validation results

**When to use:**
- Projects with automated tests
- Projects with linters/formatters
- When you want quality assurance
- Can be skipped for simple features or when tests aren't set up

**Example Invocation:**
```
Main: "@verifier-agent Validate and test the feature"

verifier-agent:
- Reads build-plans.md and engineering-progress.md
- Runs: pytest tests/
- Error: ImportError: cannot import name 'UserService' from 'services.user_service'
- Immediately knows: Engineer forgot import (from context)
- Fixes: Adds missing import statement
- Re-runs tests: Success!
- Runs: pylint services/
- Fixes: Minor linting issues
- Reports: ✅ All tests passing, linting clean
```

**Output:** Validation report + any fixes applied

**Tools:** Read, Edit, Serena, Bash, Grep

**Parallel:** ❌ NO - Only 1, runs after ALL engineers complete (if used)

### Feature-Building Workflow Steps

**Example: Multi-file feature (could be 5, 10, 20+ files)**

1. **User requests feature**
   - "Add user authentication system with login and registration"

2. **Spawn ideator-agent**
   - Investigates codebase thoroughly
   - Creates **EXHAUSTIVELY COMPREHENSIVE** feature plan
   - **Specifies exact interfaces/APIs for all files** (module paths, class names, function signatures)
   - **Explains EVERYTHING:** Every file, every function, every change needed
   - **Achieves user's objective in its entirety** - complete feature specification
   - **Doesn't worry about role distribution** - focuses on WHAT needs to happen
   - Output: build-plans.md with exhaustive details for ALL files needed (could be 5, 10, 20+ files)

3. **Spawn assigner-agent**
   - Reads build-plans.md
   - Assigns: Engineer-1 → File-1, Engineer-2 → File-2, etc.
   - Notes: All 10 have NO dependencies (interfaces specified!)
   - Output: assignments.md

4. **Spawn 10 engineer-agents IN PARALLEL**
   ```
   @engineer-agent ENGINEER_ID=1
   @engineer-agent ENGINEER_ID=2
   @engineer-agent ENGINEER_ID=3
   ...
   @engineer-agent ENGINEER_ID=10
   ```
   - All start immediately (no blocking!)
   - All work simultaneously on their files
   - Each updates engineering-progress.md when done

5. **Wait for all engineers to complete**
   - Check engineering-progress.md
   - All show "Status: COMPLETE ✓"

6. **(Optional) Spawn verifier-agent**
   ```
   @verifier-agent "Validate and test feature"
   ```
   - Reads build-plans.md and engineering-progress.md for context
   - Runs test suites (if available)
   - Fixes any issues intelligently (missing imports, syntax errors)
   - Runs linters (if configured)
   - Reports: ✅ All tests passing, code validated

   Feature complete!

**Time Comparison:**
- Sequential: 10 files × 30 min each = 300 minutes (5 hours!)
- Parallel: 30 minutes (limited by slowest engineer)
- **Speedup: 10x faster! 🚀**

### Maximum Parallelization Example

**Feature: "Add N configuration files" (example: 10 files)**

All N files independent, interfaces specified:

```
Ideator: Specifies ALL file interfaces (could be 5, 10, 20+ files)
Assigner: Creates N engineer assignments, all NO dependencies
Main: Spawns N engineers simultaneously (up to 10 max in Claude Code)

Engineer-1: ConfigA.ext ─┐
Engineer-2: ConfigB.ext  │
Engineer-3: ConfigC.ext  ├─ All work
Engineer-4: ConfigD.ext  │  simultaneously
Engineer-5: ConfigE.ext  │
Engineer-6: ConfigF.ext  │  ~30 min
Engineer-7: ConfigG.ext  │  (vs N×30 min
Engineer-8: ConfigH.ext  │   sequential)
Engineer-9: ConfigI.ext  │
Engineer-N: Config*.ext  ┘

Result: N-file feature done in ~30 minutes instead of N×30 minutes!
Speedup = N× faster (limited by slowest engineer + Claude Code's 10 agent limit)
```

### When Blocking Is Actually Needed (Rare!)

**Usually NO blocking needed** - ideator specifies interfaces!

**Only block when:**
- Need to inspect implementation logic (not just interface)
- Generated code or runtime behavior required
- Complex algorithm consumer needs to see

**Example (rare true dependency):**
```
File A: claude-pipeline/core/batch_processor.py (complex batch processing algorithm)
File B: claude-pipeline/stages/classify.py (needs to understand HOW batch processing works)

Engineer-2 must wait for Engineer-1 (true dependency)
This is uncommon - 90%+ of files can work in parallel!
```

---

## File Structure

### Bug-Fixing Workflow Files

```
.agent-results/
├── issue-tracker.md    # Diagnosed issues from diagnostic-agent
└── fix-plans.md        # Implementation plans from planning-agent
```

### Feature-Building Workflow Files

```
.agent-results/
├── build-plans.md           # Feature plans from ideator-agent
├── assignments.md           # File assignments from assigner-agent
└── engineering-progress.md  # Progress tracking by engineer-agents
```

### All files use session-based format:

```markdown
---

## Session: 1730228400

**Feature/Issue**: [Name]
**Created**: 2025-10-29T14:30:00Z
...
```

Sessions can be archived with existing session-clear command.

---

## Best Practices

### Bug-Fixing Workflow

✅ **Use full workflow for:**
- Complex bugs needing investigation
- Multiple related issues
- Want quality assurance (tests, linting)
- Need audit trail

✅ **Parallel execution (MAXIMIZE SPEED!):**
- **Multiple diagnostic-agents**: Always safe - spawn multiple for different bugs
- **Multiple planning-agents**: Always safe - spawn multiple for different issues
- **Multiple fixer-agents**: ✅ **ALWAYS spawn maximum parallel fixers!** 
  - One fixer per file/plan = maximum speed
  - Check file conflicts (usually none if fixing different files)
  - **RULE:** If 5 fixes in fix-plans.md → spawn 5 fixers simultaneously!
  - Up to 10 fixers in parallel (Claude Code limit)
- **verifier-agent**: Only 1, after ALL fixers complete (if used)

**Key Principle:** **Never wait for one fixer to finish before spawning the next!** If planning-agent created fixes for multiple files, spawn ALL fixers immediately and let them work in parallel.

✅ **Check server-memory first:**
- Look for similar bugs before diagnosing
- Use past solutions as templates

### Feature-Building Workflow

✅ **Specify interfaces upfront (ideator):**
- Module/package paths: `services.user_service` or `com.example.models`
- Class/function names: `class UserService { ... }` or `def create_user(...)`
- Function signatures: `UserService.create_user(email: str, name: str) -> User`
- Default to ZERO dependencies (specify interfaces = parallel work!)

✅ **Maximum parallelization (CRITICAL FOR SPEED!):**
- **10 files = spawn 10 engineers simultaneously!** 
- **ALWAYS spawn as many engineers as possible** - never wait for one to finish
- All start immediately if interfaces specified
- No artificial blocking
- **10x speed improvement possible!** (10 files in 30 min vs 300 min sequential)
- **RULE:** If assigner created N assignments → spawn N engineers immediately!
- Up to 10 engineers in parallel (Claude Code limit)

✅ **Dependencies should be RARE:**
- 90%+ of assignments: NO dependencies
- Only block for true implementation logic needs
- Not for interfaces (specify those upfront)

✅ **Engineer discipline:**
- Each engineer owns specific files
- No file conflicts (each file = 1 engineer)
- Simple workflow: check → work → complete

### General Best Practices

**Choose the right workflow:**
- Broken? → Bug-Fixing
- New? → Feature-Building

**Session management:**
- Sessions auto-group related work
- Use session-clear to archive old sessions
- All in single files (easy to manage)

**MCP tools:**
- Serena for semantic code operations
- Sequential-thinking for complex decisions
- Server-memory for institutional knowledge

---

## Complete Examples

### Example 1: Bug-Fixing Workflow

**Scenario:** Pipeline crashes when classifying tweets

**Step 1: Diagnosis**
```
User: "Pipeline crashes when classifying tweets - AttributeError"
Main: @diagnostic-agent "Diagnose classification crash"

diagnostic-agent:
- Finds AttributeError at claude-pipeline/stages/classify.py:167
- Identifies missing None check before accessing tweet.score
- Writes to issue-tracker.md
- Output: "Spawn planning-agent for this issue"
```

**Step 2: Planning**
```
Main: @planning-agent "Plan fix for AttributeError issue"

planning-agent:
- Reads issue from issue-tracker.md
- Designs null/None check solution for classify.py
- Writes detailed plan to fix-plans.md
- Output: "Spawn fixer-agent to implement"
```

**Step 3: Implementation (Multiple Fixers in Parallel!)**
```
Planning-agent created fixes for 3 files:
- claude-pipeline/stages/classify.py: Add None check
- backend/api/app/services/pipeline.py: Fix import error  
- web/lib/api-client.ts: Fix type mismatch

Main: Spawns ALL 3 fixers simultaneously:
  @fixer-agent "Implement fix for classify.py"
  @fixer-agent "Implement fix for pipeline.py"
  @fixer-agent "Implement fix for api-client.ts"

All 3 fixers:
- Read their assigned plans from fix-plans.md
- Work simultaneously on different files
- Complete in ~15 minutes (vs 45 minutes sequential)
- Speedup: 3x faster! ✅
```

**Step 4: Validation (Optional)**
```
Main: @verifier-agent "Validate and test fixes"

verifier-agent:
- Runs test suite: pytest tests/ for backend and claude-pipeline
- All tests pass
- Runs linter: ruff check claude-pipeline/ backend/api/
- Runs TypeScript check: npm run type-check in web/
- Reports: ✅ All tests passing, code validated
```

**Result:** Bug fixed, validated, tested in ~20 minutes

---

### Example 2: Feature-Building Workflow

**Scenario:** Add sentiment analysis pipeline stage

**Step 1: Exhaustive Planning**
```
User: "Add sentiment analysis stage to the pipeline"
Main: @ideator-agent "Design sentiment analysis feature"

ideator-agent:
- Searches server-memory for similar pipeline stage implementations
- Uses Serena to understand existing stage patterns (summarize.py, classify.py)
- Creates EXHAUSTIVELY COMPREHENSIVE plan covering EVERYTHING:
  1. claude-pipeline/stages/sentiment.py - Full stage implementation following existing patterns
  2. backend/api/app/routes/sentiment.py - FastAPI route handler
  3. backend/api/app/services/sentiment_service.py - Service layer with exact function signatures
  4. web/components/pipeline/SentimentStage.tsx - React component for UI
  5. claude-pipeline/specialized/sentiment/CLAUDE.md - Stage-specific CLAUDE.md instructions
- Specifies ALL interfaces upfront with exact code snippets
- Explains EVERY change, EVERY integration point, EVERY detail
- Achieves the user's objective in its entirety
- Doesn't worry about role distribution (assigner handles that)
- Writes exhaustive plan to build-plans.md
- Output: "5 files with complete specifications, all can work in parallel"
```

**Step 2: Distribution**
```
Main: @assigner-agent "Create engineering assignments"

assigner-agent:
- Reads build-plans.md
- Assigns:
  Engineer-1: claude-pipeline/stages/sentiment.py (no deps)
  Engineer-2: backend/api/app/routes/sentiment.py (no deps - interface known!)
  Engineer-3: backend/api/app/services/sentiment_service.py (no deps - interface known!)
  Engineer-4: web/components/pipeline/SentimentStage.tsx (no deps)
  Engineer-5: claude-pipeline/specialized/sentiment/CLAUDE.md (no deps - interfaces known!)
- Writes to assignments.md
- Output: "All 5 engineers can start immediately!"
```

**Step 3: Parallel Implementation (MAXIMUM SPEED!)**
```
Main: Spawns ALL 5 engineers IMMEDIATELY and SIMULTANEOUSLY:
  @engineer-agent ENGINEER_ID=1
  @engineer-agent ENGINEER_ID=2
  @engineer-agent ENGINEER_ID=3
  @engineer-agent ENGINEER_ID=4
  @engineer-agent ENGINEER_ID=5

All engineers:
- Check dependencies (all clear!)
- Start immediately (NO WAITING!)
- Work in parallel on their files
- Update engineering-progress.md when complete

All complete in ~30 minutes (vs 150 minutes sequential)
Speedup: 5x faster! 🚀

KEY: Never wait for Engineer-1 to finish before spawning Engineer-2!
     Spawn ALL engineers immediately for maximum parallelization!
```

**Step 4: Validation (Optional)**
```
Main: @verifier-agent "Validate and test sentiment analysis feature"

verifier-agent:
- Reads build-plans.md and engineering-progress.md for context
- Runs test suite: pytest tests/test_sentiment.py (if exists)
- Detects: Missing import in backend/api/app/routes/sentiment.py
- Fixes: Adds import from app.services.sentiment_service import SentimentService
- Re-runs tests: Success!
- Runs linter: ruff check backend/api/ claude-pipeline/
- Runs TypeScript check: npm run type-check in web/
- Fixes: Minor formatting issues
- Reports: ✅ All tests passing, code validated
```

**Result:** 5-file feature implemented in 30 minutes instead of 2.5 hours, validated and tested automatically

---

### Example 3: Maximum Parallelization

**Scenario:** N independent configuration files (example: 10)

```
User: "Add multiple configuration files for different services"

Ideator: Specifies ALL file interfaces (complete, exhaustive details)
Assigner: Creates N engineer assignments, all NO dependencies
Main: Spawns N engineers simultaneously (up to Claude Code's 10 agent limit)

All N engineers work in parallel:
- No blocking
- No waiting
- Maximum speed

Time: ~30 minutes (limited by slowest engineer)
vs N×30 minutes sequential

Speedup: N× faster! 🚀
(e.g., 10 files = 10x speedup, 20 files = 20x speedup but limited by 10 agent max)
```

---

## Migration from v5.2

**What's new in v6.0:**

Generalized for any project type:
- Removed Android-specific references (APK, devices, Gradle)
- Renamed assembler-agent → verifier-agent (optional, project-agnostic)
- Updated examples to be language/architecture agnostic
- Made verification step optional (can skip if no tests/linters)
- Focus on validation rather than deployment

**What stayed the same:**

Core workflows unchanged:
- Bug-Fixing: diagnostic → planning → fixer → [optional] verifier
- Feature-Building: ideator → assigner → engineers → [optional] verifier
- Same file structure, same parallelization benefits

**When to use what:**

- Bugs → Bug-Fixing Workflow
- Features → Feature-Building Workflow
- Verification → Optional (use if you have tests/linters/build systems)

---

## Agent Files Location

### Bug-Fixing Workflow Agents
```
.claude/agents/
├── diagnostic-agent.md
├── planning-agent.md
└── fixer-agent.md
```

### Feature-Building Workflow Agents
```
.claude/agents/
├── ideator-agent.md
├── assigner-agent.md
└── engineer-agent.md
```

### Optional Verification Agent (Both Workflows)
```
.claude/agents/
└── verifier-agent.md  ← Optional - works with BOTH workflows!
```

---

## Frequently Asked Questions

**Q: Which workflow should I use?**
A: Broken = Bug-Fixing, New = Feature-Building

**Q: Can I use bug-fixing agents for features?**
A: Not optimal. Feature-building workflow is 10x faster for new code.

**Q: Can I use feature-building agents for bugs?**
A: Not recommended. Bug-fixing workflow has systematic diagnosis.

**Q: How many engineers can work in parallel?**
A: **Up to 10 (Claude Code limit) - ALWAYS spawn maximum!** If you have 10 files, spawn 10 engineers. If you have 5 fixes, spawn 5 fixers. Maximum speed = maximum parallelization!

**Q: How many fixers can work in parallel?**
A: **Up to 10 (Claude Code limit) - ALWAYS spawn maximum!** If planning-agent created fixes for 7 files, spawn 7 fixers simultaneously. Never wait for one fixer to finish before starting the next!

**Q: What if engineers need to wait for each other?**
A: Rare if ideator specifies interfaces! Only ~10% of cases need true blocking.

**Q: Can I manually split features without ideator/assigner?**
A: Yes, but you'll miss optimizations (interface specification, dependency analysis).

**Q: Do I need to use verifier-agent after features?**
A: Optional. Use verifier-agent if:
- Your project has automated tests (it will run them)
- Your project has linters (it will run and fix issues)
- Your project has a build system (it will verify builds)
- You want automated quality checks

Skip verifier-agent if:
- Simple fixes/features where quality checks aren't needed
- No test suite or linters configured
- Manual verification preferred

---

## Revision History

- **v6.0** (2025-01-XX): Generalized for any project type - removed Android-specific references, made verifier-agent optional and project-agnostic
- **v5.2** (2025-10-29): Made assembler-agent mandatory for both workflows (not optional) - expert at fixing build errors
- **v5.1** (2025-10-29): Updated assembler-agent to work with BOTH workflows (bug-fixing and feature-building)
- **v5.0** (2025-10-29): Added Feature-Building Workflow (ideator, assigner, engineer agents)
- **v4.0** (2025-10-27): Added assembler-agent for build automation
- **v3.0** (2025-10-27): Complete redesign to 4-agent bug-fixing system
- **v2.0** (2025-10-26): 8-agent specialized system
- **v1.0** (2024): Initial agent setup

---

**For detailed agent-specific instructions, see:**

**Bug-Fixing Agents:**
- `.claude/agents/diagnostic-agent.md`
- `.claude/agents/planning-agent.md`
- `.claude/agents/fixer-agent.md`

**Feature-Building Agents:**
- `.claude/agents/ideator-agent.md`
- `.claude/agents/assigner-agent.md`
- `.claude/agents/engineer-agent.md`

**Optional Verification Agent (Both Workflows):**
- `.claude/agents/verifier-agent.md` ← Optional validation & testing for both!

---

**Summary:**
- **Bugs**: Use 3-4 agent workflow for systematic diagnosis and fixing with **MAXIMUM PARALLELIZATION** for fixers (multiple fixes = spawn multiple fixers simultaneously, up to 10)
- **Features**: Use 3-4 agent parallel workflow for maximum-speed development (**ALWAYS spawn maximum engineers** - up to 10 simultaneously = up to 10x faster!)
- **verifier-agent**: Optional validation agent that works with BOTH workflows - runs tests, linters, builds (if available)
- **CRITICAL:** **ALWAYS spawn as many fixers/engineers as possible!** Maximum speed = maximum parallelization!
- Both workflows are optimized for their specific use cases
- Choose based on whether you're fixing or building
- Use verifier-agent when you want automated quality checks (tests, linting, build verification)
- Works with any language, framework, or architecture
