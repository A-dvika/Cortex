# Setup Checklist - Bug Triage Operator

Before implementing, verify you have:

## 🔐 Required Credentials

### 1. Lemma SDK Access
- [ ] Sign up at https://lemma.work
- [ ] Get Lemma API key
- [ ] Install Lemma CLI: `npm install -g lemma`
- [ ] Verify: `lemma --version`
- [ ] Login: `lemma auth login`

**Status:** ________

### 2. Claude API Key (for Agents)
- [ ] Go to https://console.anthropic.com
- [ ] Create API key
- [ ] Set environment variable: `export ANTHROPIC_API_KEY=sk-xxx`
- [ ] Verify: `echo $ANTHROPIC_API_KEY`

**Status:** ________
**Key:** sk-...

### 3. GitHub Token (for Integration)
- [ ] Go to https://github.com/settings/tokens
- [ ] Create token with scopes: `repo`, `workflow`
- [ ] Set environment variable: `export GITHUB_TOKEN=ghp_xxx`
- [ ] Verify: `echo $GITHUB_TOKEN`

**Status:** ________
**Token:** ghp_...

### 4. Slack Workspace (Optional but Recommended)
- [ ] Have admin access to a Slack workspace
- [ ] Or create a free workspace at https://slack.com/create
- [ ] Bot token will be generated during setup

**Status:** ________

---

## 💻 System Requirements

- [ ] Node.js 18+ installed: `node --version`
- [ ] npm 8+ installed: `npm --version`
- [ ] Git installed: `git --version`
- [ ] Internet connection (for APIs)
- [ ] VS Code or editor of choice

---

## 📁 Project Setup

- [ ] Created /gappyai project directory
- [ ] Created README.md
- [ ] Created PROJECT_SPEC.md
- [ ] Created IMPLEMENTATION_GUIDE.md
- [ ] Created pod/ folder with subfolders

---

## 🚀 Ready to Begin?

Once all items above are checked, we can:

1. ✅ Create Lemma Pod
2. ✅ Create database tables
3. ✅ Build agents
4. ✅ Wire workflows
5. ✅ Test end-to-end

---

## Questions Before We Start?

**Q: Should we use Lemma Cloud or local setup?**
A: **Recommended: Lemma Cloud** (lemma.work) - easier for hackathon

**Q: Which IDE should I use?**
A: You're already in Claude Code (VS Code extension) - perfect!

**Q: Do I need to code anything?**
A: Mostly YAML configurations. Claude Code can help write them.

**Q: What if something breaks?**
A: Check TROUBLESHOOTING.md or ask in Lemma Discord

---

**Created:** June 24, 2026
**Status:** Awaiting confirmation
