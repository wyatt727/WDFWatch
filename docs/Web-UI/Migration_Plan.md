# WDFWatch Migration Plan: From CLI Pipeline to Web UI

> **Comprehensive migration strategy for transforming the current Python-based CLI pipeline into a modern web application with human-in-the-loop workflows**

---

## 🎯 Executive Summary

This document outlines the migration from the current Python CLI-based tweet pipeline to a sophisticated web application that provides real-time monitoring, human approval workflows, and quota management for the WDF podcast social engagement system.

### Current State → Target State

| Aspect | Current (CLI) | Target (Web UI) |
|--------|---------------|-----------------|
| **Interface** | Rich CLI + Basic HTML viewer | Next.js 14 web application |
| **Data Storage** | JSON files | PostgreSQL + pgvector |
| **Real-time** | None | Server-Sent Events |
| **Human Review** | CLI moderation TUI | Interactive web dashboard |
| **State Management** | File system | Database + query cache |
| **Deployment** | Docker compose scripts | Production-ready web stack |

---

## 📊 Current Architecture Analysis

### 🔍 **Strengths to Preserve**
- ✅ **Robust pipeline orchestration** via `main.py`
- ✅ **Modular task structure** in `src/wdf/tasks/`
- ✅ **Comprehensive metrics** with Prometheus
- ✅ **Mock system** for development
- ✅ **Settings management** with pydantic-settings
- ✅ **Error handling** and structured logging

### ⚠️ **Pain Points to Address**
- ❌ **File-based persistence** (transcripts/, artefacts/)
- ❌ **No real-time updates** for operators
- ❌ **Limited UI** (basic HTML viewer)
- ❌ **Manual moderation** via CLI TUI
- ❌ **No quota visualization** or read budget awareness
- ❌ **Difficult collaboration** (single operator CLI)
- ❌ **No approval audit trail**

### 📁 **Current File Structure Map**
```
WDFWatch/
├── main.py                    # Pipeline orchestrator
├── src/wdf/
│   ├── settings.py           # Configuration management
│   ├── twitter_client.py     # Twitter API abstraction
│   └── tasks/                # Pipeline tasks
│       ├── scrape.py         # Tweet scraping
│       ├── classify.py       # Gemma-3n classification
│       ├── deepseek.py       # Response generation
│       ├── moderation.py     # CLI approval interface
│       └── fewshot.py        # Few-shot generation
├── transcripts/              # File-based data store
│   ├── summary.md
│   ├── tweets.json
│   ├── classified.json
│   ├── responses.json
│   └── published.json
├── artefacts/                # Run artifacts
└── twitter_feed.html         # Basic viewer
```

---

## 🏗️ Target Architecture Overview

### **Tech Stack Selection**
| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Frontend** | Next.js 14 App Router + TypeScript | Server-side rendering, file-based routing, type safety |
| **UI Components** | shadcn/ui + Tailwind CSS | Accessible primitives, rapid development |
| **State Management** | TanStack Query + Zustand | Server state caching, minimal client state |
| **Backend API** | Next.js Route Handlers | Unified deployment, simplified auth |
| **Database** | PostgreSQL + pgvector | Relational data + vector embeddings |
| **Real-time** | Server-Sent Events | Push updates without WebSocket complexity |
| **Background Jobs** | Integrate with existing Python pipeline | Gradual migration strategy |

### **Core UI Features**
1. **Tweet Discovery Dashboard** - Real-time feed with filtering
2. **Human Approval Workflow** - Drag-and-drop style interface  
3. **Draft Editor** - Inline editing with character counts
4. **Quota Management** - Visual read budget tracking
5. **Analytics Dashboard** - Approval rates, model performance
6. **Audit Trail** - Complete action history

---

## 🛣️ Migration Strategy: 4-Phase Approach

## **Phase 1: Foundation & Data Layer** *(Weeks 1-3)*

### 🎯 **Goals**
- Establish database schema
- Create basic Next.js application structure
- Implement data migration utilities
- Maintain existing CLI pipeline

### 📋 **Tasks**

#### **1.1 Database Setup**
```sql
-- Key tables to implement
CREATE TABLE podcast_episodes (
  id SERIAL PRIMARY KEY,
  title VARCHAR(255),
  summary_text TEXT,
  keywords JSONB,
  summary_embedding vector(1536)
);

CREATE TABLE tweets (
  id SERIAL PRIMARY KEY,
  twitter_id VARCHAR(50) UNIQUE,
  author_handle VARCHAR(50),
  full_text TEXT,
  relevance_score FLOAT,
  status VARCHAR(20), -- unclassified, relevant, drafted, posted
  embedding vector(768),
  created_at TIMESTAMP
);

CREATE TABLE draft_replies (
  id SERIAL PRIMARY KEY,
  tweet_id INTEGER REFERENCES tweets(id),
  model_name VARCHAR(50),
  text TEXT,
  status VARCHAR(20), -- pending, approved, rejected
  style_score FLOAT,
  toxicity_score FLOAT,
  created_at TIMESTAMP
);
```

#### **1.2 Next.js Application Structure**
```
web/
├── app/
│   ├── (dashboard)/
│   │   ├── layout.tsx
│   │   ├── inbox/page.tsx
│   │   ├── review/page.tsx
│   │   ├── analytics/page.tsx
│   │   └── settings/page.tsx
│   ├── api/
│   │   ├── tweets/route.ts
│   │   ├── drafts/route.ts
│   │   ├── quota/route.ts
│   │   └── events/route.ts
│   └── layout.tsx
├── components/
│   ├── tweets/
│   ├── drafts/
│   ├── layout/
│   └── common/
├── lib/
│   ├── db.ts
│   ├── types.ts
│   └── api.ts
└── hooks/
    ├── useTweets.ts
    ├── useDrafts.ts
    └── useQuota.ts
```

#### **1.3 Data Migration Scripts**
```python
# scripts/migrate_data.py
def migrate_tweets_to_db():
    """Migrate tweets.json to PostgreSQL"""
    with open('transcripts/tweets.json') as f:
        tweets = json.load(f)
    
    for tweet in tweets:
        cursor.execute("""
            INSERT INTO tweets (twitter_id, author_handle, full_text, status)
            VALUES (%s, %s, %s, %s)
        """, (tweet['id'], tweet['user'], tweet['text'], 'unclassified'))

def migrate_responses_to_db():
    """Migrate responses.json to draft_replies table"""
    # Implementation details...
```

### **✅ Success Criteria**
- [ ] Database schema implemented with sample data
- [ ] Next.js app renders basic dashboard
- [ ] Data migration scripts working
- [ ] Existing CLI pipeline unchanged

---

## **Phase 2: Core UI Components** *(Weeks 4-6)*

### 🎯 **Goals**
- Implement tweet list with real-time updates
- Create draft review interface
- Build quota monitoring component
- Establish SSE event system

### 📋 **Tasks**

#### **2.1 Tweet Inbox Interface**
```tsx
// components/tweets/TweetInboxList.tsx
interface TweetInboxListProps {
  tweets: TweetListItem[];
  onSelectTweet: (id: string) => void;
  filters: FilterState;
}

export function TweetInboxList({ tweets, onSelectTweet, filters }: TweetInboxListProps) {
  return (
    <div className="space-y-2">
      {tweets.map(tweet => (
        <TweetRow 
          key={tweet.id} 
          tweet={tweet} 
          onClick={() => onSelectTweet(tweet.id)}
        />
      ))}
    </div>
  );
}
```

#### **2.2 Draft Review Panel**
```tsx
// components/drafts/DraftReviewPanel.tsx
export function DraftReviewPanel({ draft }: { draft: DraftSummary }) {
  const [editedText, setEditedText] = useState(draft.text);
  
  return (
    <div className="grid grid-cols-2 gap-6">
      <TweetContext tweet={draft.tweet} />
      <DraftEditor 
        value={editedText}
        onChange={setEditedText}
        onApprove={() => approveDraft(draft.id, editedText)}
        onReject={() => rejectDraft(draft.id)}
      />
    </div>
  );
}
```

#### **2.3 Real-time Event System**
```typescript
// lib/sse-events.ts
export type SSEEvent = 
  | { type: 'tweet_status'; tweetId: string; newStatus: string }
  | { type: 'draft_ready'; draftId: string; tweetId: string }
  | { type: 'quota_update'; used: number; remaining: number };

// Hook into existing Python pipeline events
export function emitToSSE(event: SSEEvent) {
  broadcastSSE(JSON.stringify(event));
}
```

#### **2.4 Quota Monitoring**
```tsx
// components/layout/QuotaMeter.tsx
export function QuotaMeter({ quota }: { quota: QuotaStatus }) {
  const utilizationPct = (quota.used / quota.totalAllowed) * 100;
  const isWarning = utilizationPct > 80;
  const isDanger = utilizationPct > 95;
  
  return (
    <div className={`quota-meter ${isWarning ? 'warning' : ''} ${isDanger ? 'danger' : ''}`}>
      <div className="quota-bar">
        <div 
          className="quota-fill" 
          style={{ width: `${utilizationPct}%` }}
        />
      </div>
      <span>{quota.used} / {quota.totalAllowed} reads used</span>
      {quota.projectedExhaustDate && (
        <span className="text-xs">Exhausted: {formatDate(quota.projectedExhaustDate)}</span>
      )}
    </div>
  );
}
```

### **✅ Success Criteria**
- [ ] Tweet list displays with live filtering
- [ ] Draft review workflow functional
- [ ] Real-time updates working via SSE
- [ ] Quota meter shows current usage

---

## **Phase 3: Workflow Integration** *(Weeks 7-9)* ✅ **COMPLETED**

### 🎯 **Goals** ✅
- ✅ Integrate web UI with existing Python pipeline
- ✅ Implement human-in-the-loop approval
- ✅ Add episode management interface
- ✅ Create audit logging system

### 📋 **Tasks**

#### **3.1 Pipeline Integration Bridge**
```python
# src/wdf/tasks/web_bridge.py
class WebUIBridge:
    """Bridge between Python pipeline and web UI database"""
    
    def notify_tweets_classified(self, tweets: List[Dict]):
        """Update database when classification completes"""
        for tweet in tweets:
            cursor.execute("""
                UPDATE tweets 
                SET status = %s, relevance_score = %s 
                WHERE twitter_id = %s
            """, (tweet['classification'], tweet.get('score'), tweet['id']))
            
        # Emit SSE event
        emit_sse_event({
            'type': 'tweets_classified',
            'count': len(tweets)
        })
    
    def create_draft(self, tweet_id: str, response: str, model: str):
        """Create draft in database"""
        cursor.execute("""
            INSERT INTO draft_replies (tweet_id, text, model_name, status)
            VALUES (%s, %s, %s, 'pending')
        """, (tweet_id, response, model))
        
        emit_sse_event({
            'type': 'draft_ready',
            'tweetId': tweet_id,
            'draftId': cursor.lastrowid
        })
```

#### **3.2 Approval Workflow**
```tsx
// components/drafts/ApprovalWorkflow.tsx
export function ApprovalWorkflow() {
  const { data: pendingDrafts } = useDrafts({ status: 'pending' });
  
  return (
    <div className="approval-board">
      <DraftQueue
        title="Pending Review"
        drafts={pendingDrafts}
        onApprove={handleApprove}
        onReject={handleReject}
        onEdit={handleEdit}
      />
    </div>
  );
}

async function handleApprove(draftId: string, finalText: string) {
  await api.post(`/api/drafts/${draftId}/approve`, { 
    finalText,
    scheduleAt: null // immediate posting
  });
  
  // Optimistic update
  queryClient.invalidateQueries(['drafts']);
}
```

#### **3.3 Episode Management Interface**
```tsx
// app/(dashboard)/episodes/page.tsx
export default function EpisodesPage() {
  return (
    <div className="space-y-6">
      <EpisodeUploadCard />
      <EpisodeList episodes={episodes} />
      <TranscriptProcessingStatus />
    </div>
  );
}
```

### **✅ Success Criteria**
- [x] Web UI updates when Python pipeline runs
- [x] Human approval workflow replaces CLI moderation
- [x] Episode upload and processing visible in UI
- [x] All actions logged to audit table

---

## **Phase 4: Production & Enhancement** *(Weeks 10-12)* ✅ **COMPLETED**

### 🎯 **Goals** ✅
- ✅ Optimize performance and user experience
- ✅ Implement advanced features
- ✅ Deploy production infrastructure
- ✅ Deprecate CLI interface

### 📋 **Tasks**

#### **4.1 Performance Optimization**
- **Virtual Scrolling** for large tweet lists
- **Query Optimization** with proper indexes
- **Caching Strategy** for frequently accessed data
- **Bundle Optimization** and code splitting

#### **4.2 Advanced Features**
```tsx
// components/analytics/AnalyticsDashboard.tsx
export function AnalyticsDashboard() {
  return (
    <div className="grid grid-cols-3 gap-6">
      <KPICard title="Approval Rate" value="87%" />
      <KPICard title="Avg Response Time" value="2.3s" />
      <KPICard title="Daily Quota Usage" value="450/1000" />
      
      <ChartContainer title="Daily Approval Trends">
        <ApprovalTrendChart data={approvalData} />
      </ChartContainer>
      
      <ChartContainer title="Model Performance">
        <ModelPerformanceChart data={modelData} />
      </ChartContainer>
    </div>
  );
}
```

#### **4.3 Production Deployment**
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  web:
    build: ./web
    ports: ["3000:3000"]
    environment:
      - DATABASE_URL=postgresql://...
      - REDIS_URL=redis://...
    depends_on: [db, redis]
    
  api:
    build: ./api
    ports: ["8000:8000"]
    depends_on: [db, redis]
    
  pipeline:
    build: .
    environment:
      - WDF_WEB_MODE=true
    depends_on: [db, redis, web]
```

### **✅ Success Criteria**
- [x] Production deployment successful
- [x] Performance metrics meet targets
- [x] CLI pipeline fully replaced
- [x] User training completed (via migration guide)
- [x] Advanced analytics dashboard implemented

### **✅ Completed Deliverables**
1. **Performance Optimizations**:
   - Virtual scrolling component (`VirtualTweetInboxList.tsx`)
   - Optimized API routes with caching (`/api/tweets/optimized`)
   - Performance hooks (`useOptimizedTweets.ts`)
   - Code splitting with loading states

2. **Analytics Dashboard**:
   - Comprehensive analytics API (`/api/analytics`)
   - KPI cards with trend indicators
   - Interactive charts (Approval, Model Performance, Pipeline Metrics)
   - Real-time quota usage visualization

3. **Production Infrastructure**:
   - `docker-compose.prod.yml` with full stack
   - Nginx configuration with SSL and caching
   - Monitoring with Prometheus and Grafana
   - Automated deployment script (`deploy-production.sh`)

4. **CLI Migration**:
   - Comprehensive migration guide
   - Feature comparison documentation
   - Step-by-step migration instructions
   - Rollback procedures

---

## 🔄 Data Migration Strategy

### **Migration Utilities**

#### **1. Historical Data Import**
```python
# scripts/import_historical.py
def import_artefacts():
    """Import all historical runs from artefacts/ directory"""
    for run_dir in Path('artefacts').iterdir():
        if run_dir.is_dir():
            import_run_data(run_dir)

def import_run_data(run_dir: Path):
    """Import single run's data"""
    run_id = run_dir.name
    
    # Import tweets
    if (run_dir / 'tweets.json').exists():
        import_tweets(run_dir / 'tweets.json', run_id)
    
    # Import classifications
    if (run_dir / 'classified.json').exists():
        import_classifications(run_dir / 'classified.json', run_id)
    
    # Import responses
    if (run_dir / 'responses.json').exists():
        import_responses(run_dir / 'responses.json', run_id)
```

#### **2. Real-time Sync During Transition**
```python
# src/wdf/tasks/dual_mode.py
class DualModeHandler:
    """Write to both file system and database during transition"""
    
    def save_tweets(self, tweets: List[Tweet]):
        # Legacy file-based storage
        with open('transcripts/tweets.json', 'w') as f:
            json.dump([t.model_dump() for t in tweets], f)
        
        # New database storage
        for tweet in tweets:
            self.db.insert_tweet(tweet)
        
        # Emit web UI update
        emit_sse_event({'type': 'tweets_updated', 'count': len(tweets)})
```

### **Data Validation**
```python
# scripts/validate_migration.py
def validate_data_consistency():
    """Ensure file and database data match"""
    # Compare tweet counts
    file_tweets = len(json.load(open('transcripts/tweets.json')))
    db_tweets = cursor.execute('SELECT COUNT(*) FROM tweets').fetchone()[0]
    assert file_tweets == db_tweets
    
    # Compare draft counts
    # Compare published status
    # etc.
```

---

## 🎛️ Configuration Management

### **Environment Variables**
```bash
# .env.local
DATABASE_URL=postgresql://user:pass@localhost:5432/wdfwatch
REDIS_URL=redis://localhost:6379/0
NEXTAUTH_SECRET=your-secret-here
TWITTER_API_KEY=your-twitter-key
TWITTER_API_SECRET=your-twitter-secret

# Feature flags
NEXT_PUBLIC_ENABLE_REALTIME=true
NEXT_PUBLIC_ENABLE_ANALYTICS=true
WDF_DUAL_MODE=true  # Write to both files and DB during migration
```

### **Settings Integration**
```typescript
// lib/settings.ts
interface WebUISettings {
  database: DatabaseConfig;
  features: FeatureFlags;
  integrations: IntegrationConfig;
}

export const settings = {
  database: {
    url: process.env.DATABASE_URL!,
    pool: { min: 2, max: 10 }
  },
  features: {
    realtime: process.env.NEXT_PUBLIC_ENABLE_REALTIME === 'true',
    analytics: process.env.NEXT_PUBLIC_ENABLE_ANALYTICS === 'true'
  }
};
```

---

## 🧪 Testing Strategy

### **Component Testing**
```tsx
// __tests__/components/TweetRow.test.tsx
import { render, screen } from '@testing-library/react';
import { TweetRow } from '@/components/tweets/TweetRow';

describe('TweetRow', () => {
  it('displays tweet content correctly', () => {
    const tweet = {
      id: '1',
      text: 'Test tweet content',
      user: '@testuser',
      status: 'unclassified'
    };
    
    render(<TweetRow tweet={tweet} />);
    expect(screen.getByText('Test tweet content')).toBeInTheDocument();
  });
});
```

### **API Testing**
```typescript
// __tests__/api/tweets.test.ts
import { createMocks } from 'node-mocks-http';
import handler from '@/app/api/tweets/route';

describe('/api/tweets', () => {
  it('returns tweets with correct filtering', async () => {
    const { req, res } = createMocks({
      method: 'GET',
      query: { status: 'relevant' }
    });
    
    await handler(req, res);
    
    expect(res._getStatusCode()).toBe(200);
    const data = JSON.parse(res._getData());
    expect(data.items).toHaveLength(5);
  });
});
```

### **Integration Testing**
```python
# tests/test_web_integration.py
def test_pipeline_to_web_flow():
    """Test complete flow from pipeline to web UI"""
    # Run classification task
    result = classify.run(run_id='test-123')
    
    # Check database was updated
    tweets = db.get_tweets_by_run('test-123')
    assert len(tweets) > 0
    
    # Check SSE event was emitted
    assert 'tweets_classified' in sse_events
```

---

## 📈 Performance Targets

| Metric | Target | Measurement |
|--------|---------|-------------|
| **Page Load Time** | < 2s | Lighthouse |
| **API Response Time** | < 500ms | Custom metrics |
| **Real-time Update Latency** | < 1s | SSE timing |
| **Bundle Size** | < 500KB | webpack-bundle-analyzer |
| **Database Query Time** | < 100ms | Query profiling |

---

## 🚀 Deployment Architecture

### **Production Stack**
```mermaid
graph TB
    subgraph "Load Balancer"
        LB[Nginx/Cloudflare]
    end
    
    subgraph "Web Tier"
        WEB1[Next.js App 1]
        WEB2[Next.js App 2]
    end
    
    subgraph "API Tier"
        API1[API Server 1]
        API2[API Server 2]
    end
    
    subgraph "Data Tier"
        PG[(PostgreSQL)]
        REDIS[(Redis)]
        S3[(S3/R2)]
    end
    
    subgraph "Background"
        PIPELINE[Python Pipeline]
        OLLAMA[Ollama]
    end
    
    LB --> WEB1
    LB --> WEB2
    WEB1 --> API1
    WEB2 --> API2
    API1 --> PG
    API2 --> REDIS
    PIPELINE --> PG
    PIPELINE --> OLLAMA
```

### **Infrastructure as Code**
```hcl
# terraform/main.tf
resource "aws_ecs_service" "web" {
  name            = "wdfwatch-web"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.web.arn
  desired_count   = 2
  
  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = 3000
  }
}

resource "aws_rds_instance" "main" {
  identifier     = "wdfwatch-db"
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = "db.t3.medium"
  
  allocated_storage = 100
  storage_encrypted = true
}
```

---

## ⚠️ Risk Management

### **Technical Risks**

| Risk | Impact | Mitigation |
|------|---------|------------|
| **Data Loss During Migration** | High | Dual-write mode, backups, validation scripts |
| **Performance Degradation** | Medium | Load testing, gradual rollout, monitoring |
| **Real-time System Failure** | Medium | Graceful degradation, polling fallback |
| **Database Migration Issues** | High | Schema versioning, rollback procedures |

### **Operational Risks**

| Risk | Impact | Mitigation |
|------|---------|------------|
| **User Adoption Resistance** | Medium | Training, gradual transition, feedback loops |
| **Increased Complexity** | Medium | Documentation, monitoring, automation |
| **Dependency Management** | Low | Lock files, container images, version pinning |

### **Rollback Procedures**
```bash
# Emergency rollback script
#!/bin/bash
# rollback.sh

echo "Rolling back to CLI-only mode..."

# Stop web services
docker-compose down web api

# Restore file-based data
cp backups/latest/* transcripts/

# Restart pipeline in file mode
export WDF_WEB_MODE=false
docker-compose up -d pipeline

echo "Rollback complete - CLI mode restored"
```

---

## 📋 Success Metrics

### **Technical KPIs**
- [ ] **Zero data loss** during migration
- [ ] **<2s page load times** consistently
- [ ] **99.9% uptime** for web interface
- [ ] **<1s real-time update latency**

### **User Experience KPIs**
- [ ] **Operator training completed** within 1 day
- [ ] **Approval workflow** 50% faster than CLI
- [ ] **User satisfaction** score >8/10
- [ ] **Zero critical bugs** in production

### **Business KPIs**
- [ ] **Approval throughput** increased 2x
- [ ] **Response time** to relevant tweets <5 minutes
- [ ] **False positive rate** <5% for classifications
- [ ] **Twitter read quota** utilization optimized

---

## 🎯 Conclusion

This migration plan provides a structured, risk-aware approach to transforming WDFWatch from a CLI-based pipeline into a modern web application. The 4-phase approach ensures:

1. **Minimal Disruption** - Existing pipeline continues operating
2. **Gradual Transition** - Users adapt incrementally to new interface
3. **Data Integrity** - Dual-write mode prevents loss
4. **Performance Focus** - Optimization built into every phase

### **Timeline Summary**
- **Phase 1** (Weeks 1-3): Foundation & Database
- **Phase 2** (Weeks 4-6): Core UI Components  
- **Phase 3** (Weeks 7-9): Workflow Integration
- **Phase 4** (Weeks 10-12): Production & Polish

### **Key Success Factors**
1. **Stakeholder Buy-in** - Early demo and feedback sessions
2. **Technical Excellence** - Code reviews, testing, monitoring
3. **User-Centered Design** - Operator workflow optimization
4. **Operational Readiness** - Documentation, training, support

The end result will be a sophisticated, scalable platform that dramatically improves the efficiency and reliability of the WDF podcast social engagement workflow while maintaining the robust foundation already established.

---

**Next Steps**: Begin Phase 1 implementation with database schema design and Next.js application bootstrapping.

