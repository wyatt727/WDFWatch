# WDFWatch Project Overview

## Project Purpose
WDFWatch is a comprehensive AI-powered social media engagement pipeline for the "War, Divorce, or Federalism" podcast. It automates the discovery, classification, and response generation for relevant tweets using configurable LLMs with human-in-the-loop moderation.

## Tech Stack
- **Backend**: Python with Poetry dependency management
- **Frontend**: Next.js 14 with TypeScript (Web UI migration)
- **Database**: PostgreSQL with pgvector extension
- **LLM Integration**: 
  - Claude CLI (local command-line tool) - PRIMARY
  - Ollama for local models (Gemma, DeepSeek)
  - Gemini API via CLI
- **Infrastructure**: Docker Compose with Ollama + Redis + PostgreSQL
- **Monitoring**: Prometheus metrics + Grafana
- **Testing**: pytest with parallel execution

## Claude CLI Integration
The project uses Claude CLI (command-line tool) NOT the Anthropic API. Key aspects:
- Hybrid context approach with specialized instructions + episode context
- Uses `@file` syntax for multiple context loading
- Specialized CLAUDE.md files for each pipeline stage
- Episode-specific context files for rich episode information
- Cost tracking and response caching built-in

## Current Implementation Status
- ✅ Production CLI Pipeline fully functional
- ✅ Web UI migration 95% complete (Phases 1-4)
- ✅ Claude CLI integration with hybrid context system
- ✅ API key management and safety features
- ✅ LLM model configuration management
- ✅ Keyword and scoring configuration
- 🚧 Mobile-friendly interface pending
- 🚧 Authentication system pending