Below are **detailed prop definitions** (TypeScript‑style) for all previously mentioned UI components + some supporting hooks/types. They’re grouped by domain. Each component’s *responsibility boundaries* and *prop rationale* are included so you keep concerns clean and avoid prop bloat / prop drilling. Feel free to ask for code stubs afterward.

---

## 0. Shared Primitives & Types

```ts
// Status enums
export type TweetPipelineStatus =
  | 'unclassified'
  | 'skipped'
  | 'relevant'
  | 'draft_pending'
  | 'draft_ready'
  | 'awaiting_review'
  | 'approved'
  | 'scheduled'
  | 'posted'
  | 'error';

export interface TweetListItem {
  id: string;
  authorHandle: string;
  avatarUrl?: string;
  textPreview: string;
  createdAt: string;           // ISO
  relevanceScore?: number;
  status: TweetPipelineStatus;
  hasDraft: boolean;
  flags?: {
    toxicity?: boolean;
    duplicate?: boolean;
    highRisk?: boolean;
  };
  threadCount?: number;        // for quick badge
  keywordsMatched?: string[];  // short list
}

export interface ContextSnippet {
  id: string;
  text: string;
  relevance: number; // 0..1
  sourceType: 'episode_chunk' | 'summary' | 'keyword';
}

export interface DraftSummary {
  id: string;
  model: string;
  version: number;
  createdAt: string;
  text: string;
  styleScore?: number;
  toxicityScore?: number;
  superseded?: boolean;
  promptVersion?: string;
  edited?: boolean;
}

export interface DraftVersionNode {
  version: number;
  draftId: string;
  createdAt: string;
  author: string;          // user or 'model'
  charCount: number;
  diffStats?: { added: number; removed: number; changed: number };
  toxicityScore?: number;
  approved?: boolean;
  rejected?: boolean;
}

export interface QuotaStatus {
  periodStart: string;
  periodEnd: string;
  totalAllowed: number;
  used: number;
  avgDailyUsage: number;
  projectedExhaustDate?: string;
  lastSync: string;
  sourceBreakdown: { stream: number; search: number; threadLookups: number };
}

export interface EpisodeItem {
  id: string;
  title: string;
  publishedAt?: string;
  status: 'none' | 'processing' | 'summarized' | 'keywords';
  summary?: string;
  keywords?: string[];
  progress?: number; // 0..1 if processing
  stepStatus?: Record<'upload'|'chunk'|'embed'|'summary'|'keywords',
                      'pending'|'running'|'done'|'error'>;
}

export interface KeywordToken {
  term: string;
  weight: number;       // frequency or tf-idf
  active: boolean;
  lastMatchAt?: string;
}

export interface ClassificationSimulationResult {
  probability: number;
  triggeredKeywords: string[];
  rationale?: string;
  threshold: number;
  decision: 'accept' | 'reject' | 'borderline';
}

export interface ScheduleSuggestion {
  label: string;        // e.g. "Next Hour"
  at: string;           // ISO timestamp
  reason?: string;
}

export type Severity = 'info' | 'success' | 'warning' | 'danger';

export interface AuditEvent {
  id: string;
  createdAt: string;
  actor: string;
  action: string;
  entityType: string;
  entityId: string;
  summary: string;
  diffPreview?: string;
  icon?: string;
}
```

---

## 1. Data Layer Hooks (Interfaces Only)

*(You’ll implement them with TanStack Query; listing shapes helps component props later)*

```ts
export interface UseTweetsQueryParams {
  status?: TweetPipelineStatus[];
  search?: string;
  author?: string;
  minScore?: number;
  cursor?: string;
  pageSize?: number;
  sort?: 'newest' | 'oldest' | 'score';
}

export interface PaginatedResult<T> {
  items: T[];
  nextCursor?: string;
  hasMore: boolean;
  totalFiltered?: number;
}

export interface UseTweetsQueryResult extends PaginatedResult<TweetListItem> {
  isFetching: boolean;
  refetch(): void;
}
```

---

## 2. Core List & Row Components

### `<TweetInboxList />`

**Responsibility:** Virtualized, filterable list; *no* fetching logic (parent supplies data & callbacks).

```ts
interface TweetInboxListProps {
  tweets: TweetListItem[];
  isFetching?: boolean;
  onEndReached?: () => void;            // call to fetch next page
  hasMore?: boolean;
  selectedIds?: Set<string>;
  onSelectChange?: (id: string, selected: boolean) => void;
  onSelectAllPage?: (select: boolean) => void;
  onOpen?: (tweetId: string) => void;   // open drawer
  filterBar?: React.ReactNode;          // injected filters UI
  height?: number | string;             // container height
  rowHeightEstimate?: number;
  emptyState?: React.ReactNode;
}
```

### `<TweetRow />`

**Responsibility:** Pure presentation + row-level interactions.

```ts
interface TweetRowProps {
  item: TweetListItem;
  isSelected?: boolean;
  onToggleSelect?: (id: string) => void;
  onClick?: (id: string) => void;
  compact?: boolean;
  highlightKeywords?: boolean;
  showScore?: boolean;
  disabled?: boolean;
}
```

### `<StatusBadge />`

```ts
interface StatusBadgeProps {
  status: TweetPipelineStatus;
  size?: 'sm' | 'md';
  withIcon?: boolean;
  ariaLabelOverride?: string;
}
```

### `<RelevanceScoreChip />`

```ts
interface RelevanceScoreChipProps {
  score?: number;              // 0..1
  borderlineRange?: [number, number];
  precision?: number;          // decimals displayed
  tooltip?: string;
  mutedIfUndefined?: boolean;
}
```

---

## 3. Drawer & Detail Components

### `<TweetDetailDrawer />`

**Responsibility:** Container orchestrating subpanels (context, drafts list, audit).

```ts
interface TweetDetailDrawerProps {
  tweetId: string;
  isOpen: boolean;
  onClose: () => void;
  loading?: boolean;
  tweet?: {
    id: string;
    fullText: string;
    authorHandle: string;
    createdAt: string;
    thread: { id: string; authorHandle: string; text: string }[];
    contextSnippets: ContextSnippet[];
    classificationRationale?: string;
    relevanceScore?: number;
    keywordsMatched?: string[];
    flags?: TweetListItem['flags'];
    drafts: DraftSummary[];
  };
  onGenerateDraft?: (tweetId: string) => void;
  onOpenDraft?: (draftId: string) => void;
  canGenerate?: boolean;
  quotaHint?: React.ReactNode; // e.g. cost banner
  actionsSlot?: React.ReactNode;
}
```

### `<ContextSnippetList />`

```ts
interface ContextSnippetListProps {
  snippets: ContextSnippet[];
  maxHeight?: number | string;
  showSourceType?: boolean;
  onHoverSnippet?: (id: string) => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}
```

### `<ClassificationRationale />`

```ts
interface ClassificationRationaleProps {
  rationale?: string;
  probability?: number;
  threshold?: number;
  triggeredKeywords?: string[];
  borderlineRange?: [number, number];
  collapsedInitially?: boolean;
}
```

---

## 4. Draft Review Suite

### `<DraftReviewPanel />`

**Responsibility:** Main split view for a *single* draft.

```ts
interface DraftReviewPanelProps {
  tweet: {
    id: string;
    fullText: string;
    thread?: { id: string; text: string; authorHandle: string }[];
    keywordsMatched?: string[];
  };
  draft: DraftSummary;
  versions: DraftVersionNode[];
  loadingAlternatives?: boolean;
  toxicityScore?: number;
  duplicationWarning?: string;
  maxChars?: number;
  onChangeText: (text: string) => void;
  onApproveNow: (finalText: string) => void;
  onApproveSchedule: (finalText: string) => void;
  onReject: (reason?: string) => void;
  onRegenerate: () => void;
  onRequestAlternative: (strategy: string) => void;
  onRestoreVersion: (draftId: string) => void;
  alternatives?: { id: string; label: string; text: string; strategy: string }[];
  disabled?: boolean;
  validationErrors?: string[];
  localSaving?: boolean;
  charCount?: number;
  styleScore?: number;
  actionsExtra?: React.ReactNode; // custom buttons
}
```

### `<DraftEditor />`

**Responsibility:** Controlled text editor with counters & inline macros.

```ts
interface DraftEditorProps {
  value: string;
  onChange: (value: string) => void;
  maxChars?: number;
  showCharCount?: boolean;
  highlightOverflow?: boolean;
  macros?: { label: string; token: string; description?: string }[];
  onInsertMacro?: (token: string) => void;
  readOnly?: boolean;
  ariaLabel?: string;
  autoFocus?: boolean;
  minRows?: number;
  variant?: 'plain' | 'markdown';
}
```

### `<AlternativeDraftTabs />`

```ts
interface AlternativeDraftTabsProps {
  alternatives: { id: string; label: string; text: string; strategy: string }[];
  loading?: boolean;
  onAdopt?: (id: string) => void;
  onRegenerateStrategy?: (strategy: string) => void;
  activeId?: string;
  onSelect?: (id: string) => void;
  emptyState?: React.ReactNode;
}
```

### `<DiffViewer />`

```ts
interface DiffViewerProps {
  original: string;
  modified: string;
  viewStyle?: 'side-by-side' | 'inline';
  highlightThreshold?: number; // min change to highlight
  showStats?: boolean;
  stats?: { added: number; removed: number; changed: number };
  collapsible?: boolean;
  collapsedInitially?: boolean;
  onToggleCollapse?: () => void;
  className?: string;
}
```

### `<VersionTimeline />`

```ts
interface VersionTimelineProps {
  versions: DraftVersionNode[];
  currentVersion: number;
  onSelectVersion: (version: number) => void;
  onRestoreVersion?: (version: number) => void;
  orientation?: 'vertical' | 'horizontal';
  compact?: boolean;
}
```

### `<ToxicityBadge />`

```ts
interface ToxicityBadgeProps {
  score?: number;              // 0..1
  threshold?: number;
  flagged?: boolean;           // overrides logic if set
  tooltip?: string;
  size?: 'sm' | 'md';
}
```

---

## 5. Scheduling & Posting

### `<SchedulePopover />`

```ts
interface SchedulePopoverProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  suggestions: ScheduleSuggestion[];
  onSelect: (iso: string) => void;
  onCustom: (iso: string) => void;
  minDate?: string;              // earliest allowed ISO
  defaultSuggestionId?: string;
  loading?: boolean;
  timezone?: string;
}
```

### `<PostConfirmModal />`

```ts
interface PostConfirmModalProps {
  open: boolean;
  onClose: () => void;
  tweetPreview: string;
  draftPreview: string;
  charCount: number;
  willThread?: boolean;
  onConfirm: () => void;
  submitting?: boolean;
  warnings?: string[];
}
```

---

## 6. Transcript / Episode Management

### `<EpisodeList />`

```ts
interface EpisodeListProps {
  episodes: EpisodeItem[];
  onSelect?: (episodeId: string) => void;
  onUploadClick?: () => void;
  loading?: boolean;
  selectedId?: string;
  emptyState?: React.ReactNode;
}
```

### `<EpisodeCard />`

```ts
interface EpisodeCardProps {
  episode: EpisodeItem;
  onClick?: (id: string) => void;
  selected?: boolean;
  compact?: boolean;
  showProgressRing?: boolean;
  actionsSlot?: React.ReactNode;
}
```

### `<TranscriptUploadModal />`

```ts
interface TranscriptUploadModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (file: File) => void;
  accept?: string;            // e.g. ".txt,.vtt,.srt,.mp3,.wav"
  maxSizeMB?: number;
  uploading?: boolean;
  error?: string;
  helperText?: string;
}
```

### `<ProcessingStepper />`

```ts
interface ProcessingStepperProps {
  steps: { key: string; label: string; status: 'pending'|'running'|'done'|'error'; meta?: string }[];
  compact?: boolean;
  onRetryStep?: (key: string) => void;
  showOverallProgress?: boolean;
  progress?: number; // 0..1
}
```

### `<SummaryViewer />`

```ts
interface SummaryViewerProps {
  summary?: string;
  keywords?: string[];
  loading?: boolean;
  onRegenerate?: (mode: 'concise'|'promotional'|'technical') => void;
  regenerateDisabled?: boolean;
}
```

---

## 7. Keyword / Rule Management

### `<KeywordTokenCloud />`

```ts
interface KeywordTokenCloudProps {
  tokens: KeywordToken[];
  onToggle?: (term: string, active: boolean) => void;
  maxTokens?: number;
  showWeights?: boolean;
  density?: 'normal' | 'compact';
  sortable?: boolean;
  sortBy?: 'alpha' | 'weight' | 'activity';
  onSortChange?: (v: KeywordTokenCloudProps['sortBy']) => void;
  filter?: string;
  onFilterChange?: (value: string) => void;
}
```

### `<KeywordSimulationPanel />`

```ts
interface KeywordSimulationPanelProps {
  inputText: string;
  onChangeInput: (value: string) => void;
  onRunSimulation: () => void;
  loading?: boolean;
  result?: ClassificationSimulationResult;
  threshold?: number;
}
```

---

## 8. Quota & Analytics

### `<QuotaMeter />`

```ts
interface QuotaMeterProps {
  quota: QuotaStatus;
  size?: 'sm' | 'md' | 'lg';
  showProjection?: boolean;
  onManualRefresh?: () => void;
  refreshing?: boolean;
  warnThresholdPct?: number;      // e.g. 80
  dangerThresholdPct?: number;    // e.g. 95
  inline?: boolean;
  tooltipPlacement?: 'top'|'bottom'|'left'|'right';
}
```

### `<UsageSparkline />`

```ts
interface UsageSparklineProps {
  data: { date: string; reads: number }[];
  height?: number;
  colorVariant?: 'default' | 'warning' | 'danger';
  projected?: { date: string; projectedReads: number }[];
}
```

### `<KpiCard />`

```ts
interface KpiCardProps {
  label: string;
  value: string;
  delta?: number;             // percent change
  deltaDirection?: 'up'|'down'|'flat';
  loading?: boolean;
  icon?: React.ReactNode;
  intent?: Severity;
  tooltip?: string;
  onClick?: () => void;
}
```

---

## 9. Notifications & Real-Time

### `<RealtimeToast />`

```ts
interface RealtimeToastProps {
  id: string;
  title: string;
  message?: string;
  type?: Severity;
  onDismiss?: (id: string) => void;
  autoDismissMs?: number;
  action?: { label: string; onClick: () => void };
}
```

### `<SseConnectionIndicator />`

```ts
interface SseConnectionIndicatorProps {
  status: 'connecting'|'open'|'closed'|'error';
  lastEventAt?: string;
  onReconnect?: () => void;
  inline?: boolean;
}
```

---

## 10. Forms & Validation Utilities

### `<ThresholdSlider />`

```ts
interface ThresholdSliderProps {
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onChange: (v: number) => void;
  label?: string;
  showValue?: boolean;
  disabled?: boolean;
}
```

### `<PromptTemplateViewer />`

```ts
interface PromptTemplateViewerProps {
  version: string;
  active: boolean;
  systemPrompt: string;
  userTemplate: string;
  metrics?: { approvalRate?: number; avgEditDistance?: number };
  monospaced?: boolean;
  onActivate?: () => void;
  readOnly?: boolean;
}
```

---

## 11. Audit & History

### `<AuditTimeline />`

```ts
interface AuditTimelineProps {
  events: AuditEvent[];
  loading?: boolean;
  onLoadMore?: () => void;
  hasMore?: boolean;
  dateGrouping?: 'day' | 'hour';
  filter?: { actor?: string; action?: string };
  onFilterChange?: (filter: AuditTimelineProps['filter']) => void;
}
```

### `<DiffPreviewPopover />`

```ts
interface DiffPreviewPopoverProps {
  trigger: React.ReactNode;
  diffText?: string;
  loading?: boolean;
  maxWidth?: number;
}
```

---

## 12. Utility / Layout

### `<PaneResizer />`

```ts
interface PaneResizerProps {
  direction: 'vertical' | 'horizontal';
  onResize: (sizes: [number, number]) => void;
  initialSizes?: [number, number]; // percentages or pixels
  minSizes?: [number, number];
  collapsible?: boolean;
  onCollapse?: (index: 0 | 1) => void;
}
```

### `<FilterBar />`

```ts
interface FilterBarProps {
  children?: React.ReactNode;
  onReset?: () => void;
  dirty?: boolean;
  compact?: boolean;
}
```

---

## 13. Global Dialogs / Modals

### `<RejectReasonModal />`

```ts
interface RejectReasonModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (reason: string) => void;
  submitting?: boolean;
  reasonsPreset?: string[];        // quick chips
  maxLen?: number;
}
```

### `<UnsavedChangesDialog />`

```ts
interface UnsavedChangesDialogProps {
  open: boolean;
  onDiscard: () => void;
  onCancel: () => void;
  onSaveAndLeave?: () => void;
}
```

---

## 14. State Management Patterns (Prop Guidance)

| Pattern                        | Recommendation                                                                                                       |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| **Controlled vs Uncontrolled** | Editors, selection sets, and filters should be **controlled** from parent; drawers/modals accept `open` + `onClose`. |
| **Callbacks**                  | Use stable callback names: `onChangeX`, `onSelect`, `onOpen`, `onClose` to reduce mental load.                       |
| **Loading Flags**              | Provide explicit `loading` rather than inferring from missing data (improves skeleton logic).                        |
| **Error Handling**             | UI components display errors passed via `error?: string`; fetching layer logs & translates raw errors.               |
| **Memoization**                | Keep components pure; avoid passing new inline objects each render (e.g., wrap in `useMemo`).                        |

---

## 15. Example Composition (Illustrative)

```tsx
function InboxPage() {
  const { items, hasMore, isFetching } = useTweetsQuery({ status: ['relevant','draft_ready'] });
  const [openTweetId, setOpenTweetId] = useState<string|undefined>();

  return (
    <>
      <FilterBar dirty={/* ... */} onReset={() => {/*...*/}} />
      <TweetInboxList
        tweets={items}
        isFetching={isFetching}
        hasMore={hasMore}
        onEndReached={() => {/* fetch next */}}
        onOpen={setOpenTweetId}
      />
      <TweetDetailDrawer
        tweetId={openTweetId!}
        isOpen={!!openTweetId}
        onClose={() => setOpenTweetId(undefined)}
        // other props...
      />
    </>
  );
}
```

---

## 16. Prop Anti‑Patterns to Avoid

| Anti‑Pattern                                                    | Fix                                                   |
| --------------------------------------------------------------- | ----------------------------------------------------- |
| Passing entire fetch result objects when only `items` needed    | Extract exact fields; reduces re-renders              |
| “God” component handing network + logic + layout                | Split: container hook + presentational component      |
| Boolean explosion (`showX`, `showY`, `showZ`)                   | Group into an options object or use composition slots |
| Hidden side effects in `onSelect` (e.g., also triggering fetch) | Keep side effects explicit at container level         |

---

## 17. Prioritized Implementation Order

1. **List & Row (TweetInboxList, TweetRow, StatusBadge, RelevanceScoreChip)**
2. **Drawer (TweetDetailDrawer + ContextSnippetList + ClassificationRationale)**
3. **Draft Review Suite (DraftEditor, DiffViewer, VersionTimeline, ToxicityBadge)**
4. **Scheduling (SchedulePopover, PostConfirmModal)**
5. **Episode Management (TranscriptUploadModal, ProcessingStepper, SummaryViewer)**
6. **Keyword Tools (KeywordTokenCloud, KeywordSimulationPanel)**
7. **Quota & Analytics (QuotaMeter, KpiCard, UsageSparkline)**
8. **Audit (AuditTimeline, DiffPreviewPopover)**
9. **Global Utility (RealtimeToast, SseConnectionIndicator, PaneResizer)**

---

If you want **full code skeletons** (e.g., .tsx files with styled shells), a **Zod schema map**, or a **Storybook config with example stories**, just say the word and specify which to generate first. Want any prop consolidation or additions? Let me know.
