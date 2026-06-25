# Bug Triage & Release Operator - Project Specification

> ℹ️ **Note:** This is the product *vision/spec*. Any YAML snippets below were
> written before the Lemma SDK was inspected and are **illustrative only**. The
> authoritative, working resource definitions live in
> [`cortex-triage/`](cortex-triage/) (real JSON bundle), and the
> verified build/deploy steps are in [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md).

## Executive Summary

**Product:** AI-powered GitHub issue triage system using Lemma SDK
**Target Users:** Engineering teams, open-source maintainers, DevOps teams
**Problem:** Manual bug triage takes 3-5 hours/week per team
**Solution:** Automated triage with severity scoring and fix suggestions
**Timeline:** 6 days (June 24-30, 2026)

---

## Problem Statement

### Current Pain Points

1. **Manual Triage is Time-Consuming**
   - Each issue requires reading full description
   - Engineers manually assign severity (inconsistently)
   - No automatic duplicate detection
   - Release notes written manually

2. **Severity Scoring is Inconsistent**
   - No clear criteria for P1 vs P2
   - Critical bugs might be labeled as "help wanted"
   - New team members don't know how to triage

3. **Fix Suggestions Missing**
   - No automated suggestions for what might fix it
   - Developers start from scratch for each bug
   - Similar bugs solved differently

4. **Release Notes are Incomplete**
   - Missing context about why bugs were fixed
   - Inconsistent formatting
   - Takes hours to generate

### Quantified Impact

- **Time Wasted:** 3-5 hours/week × 52 weeks = 156-260 hours/year per team
- **Cost:** At $100/hour = $15,600-26,000/year per team
- **Risk:** P1 bugs marked as P3 due to triage fatigue
- **Quality:** Release notes missing important context

---

## Solution Overview

### What We're Building

An intelligent system that:

1. **Receives** GitHub issues via webhook
2. **Analyzes** issue description, labels, code context
3. **Scores** severity based on impact + urgency
4. **Suggests** fixes using code analysis
5. **Generates** release notes automatically
6. **Notifies** team via Slack with priority

### Key Features

| Feature | Description | Impact |
|---------|-------------|--------|
| **Auto-Triage** | Classify bugs, assign severity | Save 20 min/issue |
| **Severity Scoring** | P1/P2/P3 with confidence | Consistent prioritization |
| **Duplicate Detection** | Link similar issues | Avoid duplicate work |
| **Fix Suggestions** | AI recommends solutions | 50% less thinking |
| **Release Notes** | Auto-generate summaries | Save 1-2 hours/release |
| **Dashboard** | View all triage status | Real-time visibility |
| **Slack Integration** | Get notified of P1 bugs | Instant alerting |

---

## Technical Architecture

### 1. Pod Configuration

**Name:** Bug Triage Operator
**Purpose:** Manages all agents, tables, workflows for bug triage
**Access:** GitHub webhook → Lemma Pod → Output to Slack/GitHub

### 2. Agents (4 Specialized Workers)

#### Agent 1: Bug Analyzer
```
Input:  GitHub issue (title, description, labels, comments)
Process: 
  - Parse issue text
  - Extract key information
  - Classify bug type (crash, performance, UI, doc, etc.)
  - Identify severity signals (production, user count, etc.)
Output: Structured analysis
```

**Key Signals to Extract:**
- Is production affected?
- How many users affected?
- Is there a workaround?
- Has this happened before?
- Is customer waiting?

#### Agent 2: Severity Scorer
```
Input:  Bug analysis from Agent 1
Process:
  - Apply severity rules (custom knowledge base)
  - Calculate impact score (0-100)
  - Calculate urgency score (0-100)
  - Combine into P1/P2/P3
  - Return confidence level
Output: Severity level + confidence
```

**Severity Matrix:**
- **P1 (Critical):** Production down OR > 100 users affected OR paying customer down
- **P2 (High):** > 10 users OR major feature broken OR performance critical
- **P3 (Medium):** < 10 users OR minor feature OR cosmetic issue

#### Agent 3: Fix Suggester
```
Input:  Bug description + code context (from Files)
Process:
  - Analyze code around the issue
  - Look for similar past fixes
  - Suggest potential solutions
  - Generate code snippet if applicable
  - Estimate effort + risk
Output: Fix suggestion + code
```

#### Agent 4: Release Notes Generator
```
Input:  List of fixed bugs (from Fixes table)
Process:
  - Group bugs by feature/area
  - Write clear summaries
  - Format as markdown
  - Add impact/migration notes
Output: Release notes
```

### 3. Tables (Data Storage)

#### Issues Table
```yaml
columns:
  - issue_id: string (GitHub issue #)
  - repo: string
  - title: string
  - description: text
  - url: string
  - author: string
  - created_at: datetime
  - labels: array
  - state: enum(open, closed)
  - triage_status: enum(pending, analyzing, scored, done)
```

#### Bugs Table
```yaml
columns:
  - bug_id: string (UUID)
  - issue_id: string (foreign key)
  - issue_url: string
  
  # From Analyzer
  - type: enum(crash, perf, ui, doc, other)
  - severity_signals: json (raw signals)
  
  # From Scorer
  - severity: enum(P1, P2, P3)
  - impact_score: number (0-100)
  - urgency_score: number (0-100)
  - confidence: number (0-1)
  
  # Metadata
  - analyzed_at: datetime
  - scored_at: datetime
  - is_duplicate: boolean
  - duplicate_of: string (bug_id)
```

#### Fixes Table
```yaml
columns:
  - fix_id: string (UUID)
  - bug_id: string (foreign key)
  - suggestion: text
  - code_snippet: text
  - risk_level: enum(low, medium, high)
  - estimated_effort: enum(trivial, small, medium, large)
  - suggested_at: datetime
  - agent_confidence: number (0-1)
```

#### Release_Notes Table
```yaml
columns:
  - release_id: string (UUID)
  - version: string (e.g., "2.3.0")
  - fixed_bugs: array (bug_ids)
  - release_notes: text (markdown)
  - highlights: array
  - breaking_changes: array
  - migration_guide: text
  - generated_at: datetime
```

### 4. Files (Knowledge Base)

#### Common Patterns (common-patterns.md)
```
## Crash - Null Pointer Exception
Signals: "null", "undefined", "NullPointerException"
Likely Causes: Missing validation, edge case
Fix Pattern: Add null check, default value
Similar Issues: #234, #567, #890

## Performance - Slow API
Signals: "slow", "timeout", "latency", "> 5s"
Likely Causes: N+1 query, missing index, large payload
Fix Pattern: Add caching, pagination, optimize query
Similar Issues: #123, #456
```

#### Severity Rules (severity-rules.md)
```
P1 Criteria:
- Key: "production" OR "down" OR "broken" → P1
- Key: affected_users > 100 → P1
- Key: "customer" OR "paying" → P1

P2 Criteria:
- Key: affected_users > 10 → P2
- Key: "feature broken" → P2
- Key: performance critical → P2

P3 Criteria:
- Everything else → P3
```

#### Code Context (architecture.md)
```
Service: api-gateway
├─ Entry point for all requests
├─ Error handling: try-catch in handler
├─ Common issues: CORS, auth, rate limiting
└─ Recent changes: (git log)

Service: database
├─ PostgreSQL with connection pool
├─ Common issues: deadlock, connection pool exhausted
└─ Fixes: restart pool, vacuum, reindex
```

### 5. Workflow (Orchestration)

```
MAIN WORKFLOW: Bug Triage Pipeline

[GitHub Webhook] 
    ↓
[Create Incident Row in Issues Table]
    ↓
[Bug Analyzer Agent]
    ├─ Extract: type, severity_signals
    ├─ Update: Issues.triage_status = "analyzing"
    └─ Create: Bugs row
    ↓
[Severity Scorer Agent]
    ├─ Score: impact + urgency
    ├─ Assign: P1/P2/P3 + confidence
    ├─ Update: Bugs.severity, Bugs.scored_at
    └─ Update: Issues.triage_status = "scored"
    ↓
[Function: Detect Duplicates]
    ├─ Query: similar bugs in Bugs table
    ├─ Link: Bugs.duplicate_of
    └─ Skip: Fix Suggester if duplicate
    ↓
[Fix Suggester Agent] (if not duplicate)
    ├─ Analyze: bug type, code context
    ├─ Suggest: potential fixes
    ├─ Create: Fixes row
    └─ Estimate: effort + risk
    ↓
[Decision: Severity Level?]
    ├─ P1 → [Slack Notification] (immediate)
    ├─ P2 → [Slack Notification] (summarized)
    └─ P3 → [Silent] (dashboard only)
    ↓
[GitHub Connector: Update Issue]
    ├─ Add label: P1/P2/P3
    ├─ Add comment: severity + fix suggestion
    ├─ Assign to team (if needed)
    └─ Close duplicate issues
    ↓
[Update Bugs Table: Mark Complete]
    ├─ Set: triage_status = "done"
    └─ Set: completed_at = now()
```

### 6. Connectors (External Integrations)

#### GitHub Connector
```
READS:
- Repository issues (via API)
- Pull requests
- Recent commits
- Code files

WRITES:
- Labels (P1/P2/P3)
- Comments (triage result + fix)
- Create PRs (with suggested fixes)
- Close duplicates
- Assign issues
```

#### Slack Connector
```
SENDS:
- P1 alerts immediately
- Daily digest of P2s
- Release notes ready for review
- Suggested fixes for review

LISTENS:
- User feedback ("good triage", "bad triage")
- Manual override commands
```

### 7. Functions (Deterministic Logic)

#### Function 1: Score Severity
```python
def score_severity(impact_score, urgency_score):
    combined = (impact_score * 0.6) + (urgency_score * 0.4)
    if combined > 70:
        return "P1"
    elif combined > 40:
        return "P2"
    else:
        return "P3"
```

#### Function 2: Detect Duplicates
```python
def find_duplicates(bug_description, threshold=0.85):
    # Semantic search against past bugs
    # Return similar issues with similarity score
    # If > threshold: mark as duplicate
```

#### Function 3: Generate Release Notes
```python
def generate_release_notes(fixed_bugs, version):
    grouped = group_by_feature(fixed_bugs)
    notes = format_as_markdown(grouped)
    return notes
```

### 8. Dashboard App

```
COMPONENTS:

1. Open Issues View
   ├─ Filter by severity (P1/P2/P3)
   ├─ Show triage status (analyzing → scored → done)
   ├─ Display suggested fix
   ├─ Link to GitHub issue
   └─ Action: "Create PR" button

2. Metrics Dashboard
   ├─ Issues triaged (count)
   ├─ Avg triage time
   ├─ P1 accuracy (did we correctly identify P1s?)
   ├─ Fix suggestion accuracy
   └─ Trends (improving over time)

3. Release Notes Preview
   ├─ Version number
   ├─ Fixed bugs
   ├─ Auto-generated notes
   ├─ Edit capability
   └─ Publish button

4. Duplicate Issues View
   ├─ Show linked issues
   ├─ Merge action
   └─ Consolidate duplicates
```

---

## Success Criteria

### Hackathon Judging (35% + 25% + 25% + 15% = 100%)

| Criterion | Target | How We Meet It |
|-----------|--------|-----------------|
| **Problem Clarity (35%)** | ✅ Every engineer understands | Clear, relatable problem |
| **Product Judgment (25%)** | ✅ Focused, no waste | Tight feature scope |
| **Execution Quality (25%)** | ✅ Core loop works end-to-end | Demo shows: issue → triage → result |
| **SDK Usage (15%)** | ✅ Meaningful use of Lemma | Uses agents, tables, workflow, connectors |

### Product Metrics

| Metric | Target | How We Measure |
|--------|--------|-----------------|
| Triage Time | < 3 minutes | Issue created → severity assigned |
| Severity Accuracy | > 90% | Manual review vs AI prediction |
| Fix Suggestion Accuracy | > 80% | Does fix actually solve issue? |
| Duplicate Detection | > 85% | Correctly identified similar issues? |
| Release Notes Quality | > 90% | Human review of auto-generated notes |

---

## Demo Walkthrough

### Scenario 1: Critical Bug
```
1. GitHub issue created: "API crashes on production - 500 error"
2. Webhook triggers Lemma
3. Bug Analyzer: "crash" detected, production keyword found
4. Severity Scorer: P1 (production + crash = high impact)
5. Fix Suggester: "Add error handler in request middleware"
6. Slack: 🚨 P1 alert posted
7. GitHub: Issue labeled "P1", comment with fix suggestion added
8. Dashboard: Shows triage status + suggested fix
⏱️ Total: 2 minutes (vs 30 minutes manual)
```

### Scenario 2: Duplicate
```
1. GitHub issue: "Dashboard is slow when viewing 10k records"
2. Bug Analyzer: "performance" detected
3. Severity Scorer: P2
4. Duplicate Detector: "Matches issue #234 (87% similarity)"
5. Result: Marked as duplicate, linked to original
6. Slack: Notifies that duplicate found
7. Dashboard: Shows duplicate link
⏱️ Total: 1 minute
```

### Scenario 3: Release Notes
```
1. Query: All closed issues this release
2. Release Notes Generator: Groups by feature
3. Generates markdown with: what fixed, why important, migration notes
4. Dashboard: Shows preview
5. Engineer: Clicks "Publish" → creates release PR
⏱️ Total: 2 minutes (vs 1-2 hours manual)
```

---

## Technology Stack

- **Framework:** Lemma SDK
- **Language:** YAML (Lemma configs) + JavaScript/Python (agents)
- **Database:** Lemma Tables
- **APIs:** GitHub API, Slack API, Claude API
- **Hosting:** Cloud (lemma.work) or local Docker

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Lemma SDK unfamiliar | Use docs, Discord, start with simple agents |
| AI accuracy concerns | Demo with mock data first, iterate |
| GitHub API limits | Cache responses, batch operations |
| Time management | Prioritize MVP (analyzer + scorer + workflow) |

---

## Success Path to Hiring

**How this impresses hiring partners (YesMadam, Binocs, Foxo, Zapdata, Corally):**

1. ✅ **Shows Product Thinking:** Clear problem → focused solution
2. ✅ **Shows Shipping Mentality:** Built in 6 days, works end-to-end
3. ✅ **Shows Technical Depth:** Multi-agent system, integrations
4. ✅ **Shows Communication:** Blog posts explaining the build
5. ✅ **Shows AI/LLM Thinking:** Effective use of Claude for agents

**Roles we'd be considered for:**
- AI Product Engineer (building AI-powered features)
- AI Product Manager (understanding AI workflows + product)
- Senior Engineer (architecture, systems thinking)

---

**Document Created:** June 24, 2026
**Status:** 🟢 Live
