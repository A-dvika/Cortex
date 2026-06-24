# Bug Triage Operator - Implementation Guide

Step-by-step guide to building the complete system in 6 days.

## 📅 Daily Breakdown

### Day 1 (June 24): Setup & Core Infrastructure ✅ IN PROGRESS
- [x] Project documentation (README, SPEC, ARCHITECTURE)
- [ ] Lemma environment setup
- [ ] Create Pod and basic configuration
- [ ] Create 4 database tables
- [ ] Create knowledge base files

### Day 2 (June 25): Build Agents
- [ ] Bug Analyzer Agent
- [ ] Severity Scorer Agent
- [ ] Fix Suggester Agent
- [ ] Release Notes Generator Agent

### Day 3 (June 26): Workflow & Integrations
- [ ] Wire main workflow
- [ ] GitHub connector setup
- [ ] Slack connector setup
- [ ] Test workflow end-to-end

### Day 4 (June 27): App & Dashboard
- [ ] Create dashboard app
- [ ] Build UI components
- [ ] Add metrics tracking
- [ ] Integrate with workflow

### Day 5 (June 28): Mock Infrastructure & Testing
- [ ] Create mock GitHub repo
- [ ] Build demo scenario
- [ ] Write demo script
- [ ] Test all workflows

### Day 6 (June 29-30): Polish & Submission
- [ ] Create demo video
- [ ] Write blog post
- [ ] Prepare submission materials
- [ ] Final review and refinement

---

## 🔧 Step-by-Step Implementation

### PHASE 1: Environment Setup (2-3 hours)

#### Step 1.1: Install Lemma CLI
```bash
# Check if node is installed
node --version

# Install Lemma CLI
npm install -g lemma

# Verify installation
lemma --version

# Login to Lemma
lemma auth login
```

#### Step 1.2: Create Project Structure
```bash
cd c:/Users/HP/Documents/gappyai

# Create folders
mkdir -p pod/{tables,agents,files,workflow,connectors,app}
mkdir -p mock
mkdir -p docs

# Verify structure
ls -la
```

#### Step 1.3: Initialize Lemma Pod
```bash
# Create pod
lemma pod create bug-triage-operator \
  --description "AI-powered GitHub issue triage system"

# Get pod ID (save this!)
lemma pod list
# Example: POD_ID=pod_xxxxx

# Export for later use
export POD_ID=pod_xxxxx
```

---

### PHASE 2: Create Database Tables (2 hours)

#### Step 2.1: Issues Table
Create `pod/tables/issues-table.yaml`:
```yaml
name: issues
description: "GitHub issues awaiting triage"
columns:
  - name: issue_id
    type: string
    required: true
    description: "GitHub issue number"
  - name: repo
    type: string
    required: true
    description: "Repository name"
  - name: title
    type: string
    required: true
    description: "Issue title"
  - name: description
    type: text
    required: true
    description: "Full issue description"
  - name: url
    type: string
    required: true
    description: "GitHub issue URL"
  - name: author
    type: string
    required: true
    description: "Who opened the issue"
  - name: created_at
    type: datetime
    required: true
  - name: labels
    type: array
    description: "GitHub labels"
  - name: state
    type: string
    enum: ["open", "closed"]
    default: "open"
  - name: triage_status
    type: string
    enum: ["pending", "analyzing", "scored", "done"]
    default: "pending"
```

Deploy:
```bash
cd pod/tables
lemma table create \
  --pod-id $POD_ID \
  --payload-file issues-table.yaml
```

#### Step 2.2: Bugs Table
Create `pod/tables/bugs-table.yaml`:
```yaml
name: bugs
description: "Triaged and scored bugs"
columns:
  - name: bug_id
    type: string
    required: true
  - name: issue_id
    type: string
    required: true
    description: "Foreign key to issues table"
  - name: issue_url
    type: string
  - name: type
    type: string
    enum: ["crash", "perf", "ui", "doc", "other"]
  - name: severity
    type: string
    enum: ["P1", "P2", "P3"]
  - name: impact_score
    type: number
    description: "0-100 impact assessment"
  - name: urgency_score
    type: number
    description: "0-100 urgency assessment"
  - name: confidence
    type: number
    description: "0-1 confidence in scoring"
  - name: is_duplicate
    type: boolean
    default: false
  - name: duplicate_of
    type: string
    description: "bug_id if duplicate"
  - name: analyzed_at
    type: datetime
  - name: scored_at
    type: datetime
```

Deploy:
```bash
lemma table create \
  --pod-id $POD_ID \
  --payload-file bugs-table.yaml
```

#### Step 2.3: Fixes Table
Create `pod/tables/fixes-table.yaml`:
```yaml
name: fixes
description: "Suggested fixes for bugs"
columns:
  - name: fix_id
    type: string
    required: true
  - name: bug_id
    type: string
    required: true
  - name: suggestion
    type: text
    description: "Fix suggestion text"
  - name: code_snippet
    type: text
    description: "Code example"
  - name: risk_level
    type: string
    enum: ["low", "medium", "high"]
  - name: estimated_effort
    type: string
    enum: ["trivial", "small", "medium", "large"]
  - name: agent_confidence
    type: number
    description: "0-1 confidence"
  - name: suggested_at
    type: datetime
```

Deploy:
```bash
lemma table create \
  --pod-id $POD_ID \
  --payload-file fixes-table.yaml
```

#### Step 2.4: Release Notes Table
Create `pod/tables/release-notes-table.yaml`:
```yaml
name: release_notes
description: "Generated release notes"
columns:
  - name: release_id
    type: string
    required: true
  - name: version
    type: string
    required: true
    description: "Version number (e.g., 2.3.0)"
  - name: fixed_bugs
    type: array
    description: "Array of bug IDs"
  - name: release_notes
    type: text
    description: "Markdown release notes"
  - name: highlights
    type: array
    description: "Key highlights"
  - name: breaking_changes
    type: array
    description: "Breaking changes"
  - name: migration_guide
    type: text
  - name: generated_at
    type: datetime
```

Deploy:
```bash
lemma table create \
  --pod-id $POD_ID \
  --payload-file release-notes-table.yaml
```

---

### PHASE 3: Create Knowledge Base Files (1 hour)

#### Step 3.1: Common Patterns
Create `pod/files/common-patterns.md`:
```markdown
# Common Bug Patterns

## Crash - Null Pointer Exception
- **Signals:** "null", "undefined", "NullPointerException", "TypeError"
- **Likely Causes:** Missing validation, edge case, uninitialized variable
- **Fix Pattern:** Add null check, provide default value, validate input
- **Similar Issues:** #234, #567, #890

## Performance - Slow API
- **Signals:** "slow", "timeout", "latency", "> 5s", "performance"
- **Likely Causes:** N+1 query, missing index, large payload, inefficient algorithm
- **Fix Pattern:** Add caching, pagination, optimize query, use async
- **Similar Issues:** #123, #456, #789

## Performance - Memory Leak
- **Signals:** "memory", "leak", "OOM", "out of memory", "growing"
- **Likely Causes:** Unclosed connections, event listener not removed, circular refs
- **Fix Pattern:** Cleanup listeners, close connections, break cycles

## Auth Issue
- **Signals:** "401", "403", "Unauthorized", "Forbidden", "CORS"
- **Likely Causes:** Token expired, missing header, wrong scope, CORS misconfigured
- **Fix Pattern:** Refresh token, add header, update CORS config

## Data Loss
- **Signals:** "data", "lost", "missing", "deleted", "gone"
- **Likely Causes:** No backup, cascading delete, unhandled exception
- **Fix Pattern:** Add backup, add safeguards, validate before delete
```

#### Step 3.2: Severity Rules
Create `pod/files/severity-rules.md`:
```markdown
# Severity Classification Rules

## P1 (Critical) - Page Down

### Must Match At Least One:
- Keyword: "production" OR "down" OR "broken" OR "outage"
- Affected Users: > 100 users
- Business Impact: "paying customer" OR "revenue" OR "SLA"
- Data Loss: "data lost" OR "corruption"

### Examples:
- "API is completely down, returning 500 for all requests" → P1
- "Payment processing broken, customers can't pay" → P1
- "Production database corrupted, data loss" → P1

## P2 (High) - Feature Broken

### Must Match At Least One:
- Affected Users: > 10 users
- Impact: "feature broken" OR "doesn't work"
- Performance: "latency > 2s" OR "timeout"
- Security: "vulnerability" OR "exploit"

### Examples:
- "Dashboard slow when loading 10k records" → P2
- "Login button doesn't work on mobile" → P2
- "Export feature broken for large files" → P2

## P3 (Medium) - Minor Issue

### Everything Else:
- Small number of affected users
- Cosmetic issues
- Nice-to-have improvements
- Typos, documentation

### Examples:
- "Typo in error message" → P3
- "Button color could be better" → P3
- "Missing documentation" → P3
```

#### Step 3.3: Fix Templates
Create `pod/files/fix-templates.md`:
```markdown
# Common Fix Patterns

## Template 1: Add Error Handler
```javascript
// BEFORE
const result = await fetchData();
return result;

// AFTER
try {
  const result = await fetchData();
  if (!result) throw new Error("No data returned");
  return result;
} catch (error) {
  logger.error("Failed to fetch data", error);
  return null;
}
```

## Template 2: Add Caching
```javascript
// BEFORE
const getData = async () => {
  return await expensiveQuery();
};

// AFTER
const cache = {};
const getData = async () => {
  if (cache.data && !isExpired(cache.timestamp)) {
    return cache.data;
  }
  cache.data = await expensiveQuery();
  cache.timestamp = Date.now();
  return cache.data;
};
```

## Template 3: Add Validation
```javascript
// BEFORE
const processUser = (user) => {
  return user.name.toUpperCase();
};

// AFTER
const processUser = (user) => {
  if (!user || !user.name) {
    throw new Error("User or name is required");
  }
  return user.name.toUpperCase();
};
```
```

---

### PHASE 4: Build Agents (4-5 hours)

#### Step 4.1: Bug Analyzer Agent
Create `pod/agents/bug-analyzer.yaml`:
```yaml
name: bug-analyzer
description: "Analyzes GitHub issues and classifies them"
instructions: |
  You are a bug analyst. Read the GitHub issue description and:
  
  1. Classify the bug type (crash, performance, ui, doc, other)
  2. Extract key severity signals:
     - Is production affected? (true/false)
     - How many users affected? (estimate)
     - Is there a workaround? (true/false)
     - Customer impact? (critical/high/medium/low)
     - Keyword severity signals (urgent, blocking, asap, etc.)
  
  3. Return JSON:
  {
    "type": "crash|perf|ui|doc|other",
    "severity_signals": {
      "production_affected": boolean,
      "users_affected": number,
      "has_workaround": boolean,
      "customer_impact": "critical|high|medium|low",
      "keyword_signals": string[]
    },
    "confidence": 0.0-1.0,
    "reasoning": "explanation of classification"
  }

runtimes:
  - claude-3-5-sonnet

access_scope:
  read:
    - issues
    - bugs
  write:
    - bugs
```

Deploy:
```bash
cd pod/agents
lemma agent create \
  --pod-id $POD_ID \
  --payload-file bug-analyzer.yaml
```

#### Step 4.2: Severity Scorer Agent
Create `pod/agents/severity-scorer.yaml`:
```yaml
name: severity-scorer
description: "Scores bug severity (P1/P2/P3)"
instructions: |
  You are a severity scorer. Using the bug analysis:
  
  1. Apply these rules (from severity-rules.md):
     - P1: production down OR >100 users OR paying customer down
     - P2: >10 users OR feature broken OR latency issue
     - P3: everything else
  
  2. Calculate scores:
     - impact_score: 0-100 (how bad if it happens)
     - urgency_score: 0-100 (how soon needs fixing)
     - combined = (impact * 0.6) + (urgency * 0.4)
  
  3. Return JSON:
  {
    "severity": "P1|P2|P3",
    "impact_score": number,
    "urgency_score": number,
    "confidence": 0.0-1.0,
    "reasoning": "why this severity level"
  }

runtimes:
  - claude-3-5-sonnet

access_scope:
  read:
    - bugs
    - files  # Read severity rules
  write:
    - bugs
```

Deploy:
```bash
lemma agent create \
  --pod-id $POD_ID \
  --payload-file severity-scorer.yaml
```

#### Step 4.3: Fix Suggester Agent
Create `pod/agents/fix-suggester.yaml`:
```yaml
name: fix-suggester
description: "Suggests fixes for bugs"
instructions: |
  You are a fix suggester. For this bug:
  
  1. Analyze the issue description
  2. Look for common patterns in knowledge base
  3. Suggest 1-3 potential fixes
  4. For each fix:
     - Describe what to do
     - Provide code snippet if applicable
     - Estimate risk level (low/medium/high)
     - Estimate effort (trivial/small/medium/large)
  
  Return JSON:
  {
    "suggestions": [
      {
        "title": "Fix title",
        "description": "What to do",
        "code_snippet": "code example",
        "risk_level": "low|medium|high",
        "estimated_effort": "trivial|small|medium|large",
        "confidence": 0.0-1.0
      }
    ]
  }

runtimes:
  - claude-3-5-sonnet

access_scope:
  read:
    - bugs
    - files  # Read fix templates and patterns
  write:
    - fixes
```

Deploy:
```bash
lemma agent create \
  --pod-id $POD_ID \
  --payload-file fix-suggester.yaml
```

#### Step 4.4: Release Notes Generator Agent
Create `pod/agents/release-notes-generator.yaml`:
```yaml
name: release-notes-generator
description: "Generates release notes from fixed bugs"
instructions: |
  You are a release notes writer. Given a list of fixed bugs:
  
  1. Group them by feature/area
  2. For each group, write a clear summary
  3. Highlight user-facing changes
  4. Warn about breaking changes
  5. Provide migration guide if needed
  
  Return JSON:
  {
    "release_notes": "markdown formatted release notes",
    "highlights": ["highlight 1", "highlight 2"],
    "breaking_changes": ["breaking change 1"],
    "migration_guide": "guide text if breaking changes"
  }

runtimes:
  - claude-3-5-sonnet

access_scope:
  read:
    - bugs
    - fixes
  write:
    - release_notes
```

Deploy:
```bash
lemma agent create \
  --pod-id $POD_ID \
  --payload-file release-notes-generator.yaml
```

---

### PHASE 5: Wire Workflow (2-3 hours)

#### Step 5.1: Create Main Workflow
Create `pod/workflow/bug-triage-workflow.yaml`:
```yaml
name: bug-triage-workflow
description: "Main workflow: Issue → Analyze → Score → Suggest Fix → Release Notes"

triggers:
  - type: webhook
    name: github-issue-webhook
    description: "GitHub issue created/updated"

steps:
  - step_id: 1
    name: "Create Issue Record"
    type: table_write
    table: issues
    data:
      issue_id: ${webhook.issue_number}
      repo: ${webhook.repo_name}
      title: ${webhook.issue_title}
      description: ${webhook.issue_description}
      url: ${webhook.issue_url}
      author: ${webhook.issue_author}
      created_at: ${webhook.created_at}
      labels: ${webhook.labels}
      triage_status: "pending"

  - step_id: 2
    name: "Run Bug Analyzer"
    type: agent
    agent: bug-analyzer
    input:
      issue_title: ${steps.1.data.title}
      issue_description: ${steps.1.data.description}
    output_var: analysis

  - step_id: 3
    name: "Update Issue Status"
    type: table_update
    table: issues
    where:
      issue_id: ${steps.1.data.issue_id}
    set:
      triage_status: "analyzing"

  - step_id: 4
    name: "Create Bug Record"
    type: table_write
    table: bugs
    data:
      bug_id: ${uuid()}
      issue_id: ${steps.1.data.issue_id}
      issue_url: ${steps.1.data.url}
      type: ${analysis.type}
      severity_signals: ${analysis.severity_signals}
      analyzed_at: ${now()}

  - step_id: 5
    name: "Run Severity Scorer"
    type: agent
    agent: severity-scorer
    input:
      bug_analysis: ${analysis}
    output_var: scoring

  - step_id: 6
    name: "Update Bug with Severity"
    type: table_update
    table: bugs
    where:
      bug_id: ${steps.4.data.bug_id}
    set:
      severity: ${scoring.severity}
      impact_score: ${scoring.impact_score}
      urgency_score: ${scoring.urgency_score}
      confidence: ${scoring.confidence}
      scored_at: ${now()}

  - step_id: 7
    name: "Check for Duplicates"
    type: function
    function: detect_duplicates
    input:
      description: ${steps.1.data.description}
    output_var: duplicate_check

  - step_id: 8
    name: "Update Duplicate Status"
    type: table_update
    table: bugs
    where:
      bug_id: ${steps.4.data.bug_id}
    set:
      is_duplicate: ${duplicate_check.is_duplicate}
      duplicate_of: ${duplicate_check.duplicate_of}

  - step_id: 9
    name: "Decision: Skip if Duplicate"
    type: condition
    if: ${duplicate_check.is_duplicate == true}
    then: skip_to_step(13)

  - step_id: 10
    name: "Run Fix Suggester"
    type: agent
    agent: fix-suggester
    input:
      bug_type: ${analysis.type}
      description: ${steps.1.data.description}
    output_var: fixes

  - step_id: 11
    name: "Create Fix Record"
    type: table_write
    table: fixes
    data:
      fix_id: ${uuid()}
      bug_id: ${steps.4.data.bug_id}
      suggestion: ${fixes.suggestions[0].description}
      code_snippet: ${fixes.suggestions[0].code_snippet}
      risk_level: ${fixes.suggestions[0].risk_level}
      estimated_effort: ${fixes.suggestions[0].estimated_effort}
      agent_confidence: ${fixes.suggestions[0].confidence}
      suggested_at: ${now()}

  - step_id: 12
    name: "Decision: Notify if P1"
    type: condition
    if: ${scoring.severity == "P1"}
    then: execute_step(13)
    else: skip_to_step(15)

  - step_id: 13
    name: "Send Slack Alert (P1)"
    type: connector
    connector: slack
    action: post_message
    data:
      channel: "#critical-alerts"
      message: |
        🚨 P1 BUG DETECTED
        Title: ${steps.1.data.title}
        Severity: ${scoring.severity}
        Fix: ${fixes.suggestions[0].description}
        URL: ${steps.1.data.url}

  - step_id: 14
    name: "Update GitHub (Add Label + Comment)"
    type: connector
    connector: github
    action: update_issue
    data:
      repo: ${steps.1.data.repo}
      issue_id: ${steps.1.data.issue_id}
      labels_add: ["${scoring.severity}"]
      comment: |
        **Automated Triage**
        Severity: ${scoring.severity}
        Type: ${analysis.type}
        
        **Suggested Fix:**
        ${fixes.suggestions[0].description}
        
        ```
        ${fixes.suggestions[0].code_snippet}
        ```

  - step_id: 15
    name: "Mark Triage Complete"
    type: table_update
    table: issues
    where:
      issue_id: ${steps.1.data.issue_id}
    set:
      triage_status: "done"

  - step_id: 16
    name: "Complete"
    type: log
    message: "Triage complete for ${steps.1.data.issue_id}"
```

Deploy:
```bash
cd pod/workflow
lemma workflow create \
  --pod-id $POD_ID \
  --payload-file bug-triage-workflow.yaml
```

---

### PHASE 6: Setup Connectors (1-2 hours)

#### Step 6.1: GitHub Connector
Create `pod/connectors/github-connector.yaml`:
```yaml
name: github-connector
description: "GitHub integration for reading and updating issues"
type: github
authentication:
  type: oauth
  scopes:
    - "repo"  # Read/write issues, PRs
    - "workflow"  # Trigger workflows if needed

webhooks:
  - event: issues.opened
    path: /github/issues/opened
  - event: issues.edited
    path: /github/issues/edited

actions:
  - action: list_issues
    endpoint: GET /repos/{owner}/{repo}/issues
  - action: create_comment
    endpoint: POST /repos/{owner}/{repo}/issues/{issue_number}/comments
  - action: update_issue
    endpoint: PATCH /repos/{owner}/{repo}/issues/{issue_number}
  - action: add_labels
    endpoint: POST /repos/{owner}/{repo}/issues/{issue_number}/labels
  - action: create_pull_request
    endpoint: POST /repos/{owner}/{repo}/pulls

access_scope:
  - issues (read, write)
  - pulls (read)
  - repository_data (read)
```

Deploy:
```bash
lemma connector create \
  --pod-id $POD_ID \
  --payload-file github-connector.yaml

# Follow prompts to authenticate with GitHub
```

#### Step 6.2: Slack Connector
Create `pod/connectors/slack-connector.yaml`:
```yaml
name: slack-connector
description: "Slack integration for notifications"
type: slack
authentication:
  type: bot_token
  scopes:
    - "chat:write"
    - "channels:read"

actions:
  - action: post_message
    endpoint: POST chat.postMessage
  - action: post_thread_reply
    endpoint: POST chat.postMessage
  - action: create_channel
    endpoint: POST conversations.create

access_scope:
  - channels (read)
  - messages (write)
```

Deploy:
```bash
lemma connector create \
  --pod-id $POD_ID \
  --payload-file slack-connector.yaml

# Follow prompts to authenticate with Slack
```

---

### PHASE 7: Create Functions (1 hour)

#### Step 7.1: Duplicate Detection Function
Create `pod/functions/detect-duplicates.js`:
```javascript
// Detect duplicate issues
module.exports = async function detectDuplicates(bugDescription, threshold = 0.85) {
  const Lemma = require("@lemma-ai/sdk");
  const client = new Lemma.Client();
  
  // Query bugs table for similar issues
  const existingBugs = await client.tables.query("bugs", {
    limit: 100
  });
  
  // Simple similarity check (in production, use semantic similarity)
  const similarities = existingBugs.map(bug => ({
    bug_id: bug.bug_id,
    similarity: calculateSimilarity(bugDescription, bug.description)
  }));
  
  const match = similarities
    .sort((a, b) => b.similarity - a.similarity)
    .find(s => s.similarity > threshold);
  
  return {
    is_duplicate: !!match,
    duplicate_of: match?.bug_id,
    similarity_score: match?.similarity
  };
};

function calculateSimilarity(text1, text2) {
  // Simple word overlap (in production, use semantic similarity with embeddings)
  const words1 = new Set(text1.toLowerCase().split(/\s+/));
  const words2 = new Set(text2.toLowerCase().split(/\s+/));
  const overlap = [...words1].filter(w => words2.has(w)).length;
  return overlap / Math.max(words1.size, words2.size);
}
```

#### Step 7.2: Severity Validation Function
Create `pod/functions/validate-severity.js`:
```javascript
module.exports = function validateSeverity(impacts Score, urgencyScore) {
  const combined = (impactScore * 0.6) + (urgencyScore * 0.4);
  
  if (combined > 70) return { severity: "P1", adjusted: false };
  if (combined > 40) return { severity: "P2", adjusted: false };
  return { severity: "P3", adjusted: false };
};
```

---

## 🚀 Next Steps

After completing this guide:

1. **Test each component** as you build
2. **Use Lemma Dashboard** to monitor workflow runs
3. **Create mock GitHub issues** to test the workflow
4. **Refine agent instructions** based on results
5. **Build the dashboard app** (next phase)

## 🔗 Reference Links

- [Lemma Docs](https://lemma.work/docs)
- [GitHub API Docs](https://docs.github.com/en/rest)
- [Slack API Docs](https://api.slack.com)

---

**Status:** 🟢 In Progress
**Last Updated:** June 24, 2026
