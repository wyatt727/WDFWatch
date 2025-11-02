# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) documenting key architectural decisions made during the development of WDFWatch.

## What are ADRs?

ADRs are documents that capture important architectural decisions, including:
- The context and motivation for the decision
- The alternatives considered
- The decision made and its consequences
- Status and evolution over time

## ADR Index

### ADR-001: FastAPI Migration
**Status**: Completed  
**Date**: 2025-01-XX  
**Summary**: Migration from Next.js API routes to FastAPI backend for Claude pipeline operations.

**Decision**: Adopt FastAPI as the primary backend API service for all Claude pipeline operations, while maintaining Next.js for the web UI.

**Rationale**:
- Better Python integration for Claude CLI operations
- Improved performance for long-running pipeline jobs
- Better job queue management with RQ
- Separation of concerns (API vs UI)

**Alternatives Considered**:
- Continue with Next.js API routes (rejected - poor Python integration)
- Separate Python microservice (rejected - unnecessary complexity)

**Consequences**:
- Requires Docker Compose or separate service management
- Need to maintain two codebases (Python backend, TypeScript frontend)
- Improved scalability and maintainability

---

### ADR-002: Server-Sent Events (SSE) Strategy
**Status**: Completed  
**Date**: 2025-01-XX  
**Summary**: Use FastAPI SSE for real-time pipeline updates instead of WebSockets.

**Decision**: Use Server-Sent Events (SSE) from FastAPI backend for real-time pipeline progress updates.

**Rationale**:
- Simpler implementation than WebSockets
- Unidirectional communication (server → client) fits use case
- Built-in reconnection support
- Works well with HTTP/2

**Alternatives Considered**:
- WebSockets (rejected - unnecessary complexity)
- Polling (rejected - inefficient, high latency)
- Next.js SSE (rejected - removed legacy support)

**Consequences**:
- Single connection per episode
- Browser connection limits may apply
- Simple fallback to polling if needed

---

### ADR-003: Queue Processor Redesign
**Status**: Completed  
**Date**: 2025-01-XX  
**Summary**: Migrate queue processing from standalone script to FastAPI service.

**Decision**: Move `TweetQueueProcessor` from `src/wdf/tasks/queue_processor.py` to `backend/api/app/services/tweet_queue.py`.

**Rationale**:
- Centralize queue processing in FastAPI backend
- Better integration with job queue system
- Improved error handling and retry logic
- Consistent with other backend services

**Alternatives Considered**:
- Keep as standalone script (rejected - poor integration)
- Separate microservice (rejected - unnecessary)

**Consequences**:
- Queue processing now runs within FastAPI worker context
- Better monitoring and observability
- Easier to scale workers

---

### ADR-004: Pipeline Result Caching
**Status**: Completed  
**Date**: 2025-01-XX  
**Summary**: Implement Redis-backed caching for pipeline run results.

**Decision**: Cache pipeline run results in Redis with 24-hour TTL, keyed by episode_id and stages signature.

**Rationale**:
- Avoid redundant pipeline executions
- Reduce Claude API costs
- Improve response times for repeated requests
- Configurable cache invalidation

**Alternatives Considered**:
- Database caching (rejected - slower, more overhead)
- File-based caching (rejected - not shared across workers)
- No caching (rejected - inefficient)

**Consequences**:
- Requires Redis for caching
- Cache invalidation strategy needed
- Potential stale data issues (mitigated by TTL)

---

### ADR-005: Retry Strategy with Exponential Backoff
**Status**: Completed  
**Date**: 2025-01-XX  
**Summary**: Implement exponential backoff retry policy for failed jobs.

**Decision**: Use RQ's built-in retry mechanism with custom exponential backoff intervals (30s, 60s, 120s).

**Rationale**:
- Handle transient failures gracefully
- Reduce load on external services
- Prevent retry storms
- Configurable retry limits

**Alternatives Considered**:
- Fixed retry delay (rejected - less efficient)
- Linear backoff (rejected - slower recovery)
- No retries (rejected - poor reliability)

**Consequences**:
- Jobs may take longer to complete on retry
- Need to distinguish transient vs permanent failures
- Event tracking for retry attempts

---

### ADR-006: Structured Logging with JSON Format
**Status**: Completed  
**Date**: 2025-01-XX  
**Summary**: Adopt structlog for structured JSON logging in production.

**Decision**: Use `structlog` for structured logging with JSON output in production, console output in development.

**Rationale**:
- Better log aggregation and analysis
- Structured data extraction
- Trace ID and job ID correlation
- Production-ready logging format

**Alternatives Considered**:
- Standard Python logging (rejected - unstructured)
- Logfmt format (rejected - less common)
- Custom logging (rejected - reinventing wheel)

**Consequences**:
- Requires structlog dependency
- Learning curve for structured logging
- Better observability and debugging

---

## Template for New ADRs

When creating a new ADR, use this template:

```markdown
# ADR-XXX: [Title]

**Status**: [Proposed | Accepted | Rejected | Deprecated | Superseded]  
**Date**: YYYY-MM-DD  
**Deciders**: [List of decision makers]

## Context

[Describe the issue motivating this decision]

## Decision

[State the decision that is being made]

## Rationale

[Explain why this decision was made]

## Alternatives Considered

- [Alternative 1] - [Why it was rejected]
- [Alternative 2] - [Why it was rejected]

## Consequences

- [Consequence 1]
- [Consequence 2]
- [Consequence 3]
```

## References

- [ADR Template](https://adr.github.io/)
- [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)

