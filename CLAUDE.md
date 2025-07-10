# Claude Instructions - Master Navigation Hub

## 🚨 CRITICAL OPERATIONAL RULES

### Default Mode
- **PLAN MODE IS THE DEFAULT** - Always enter plan mode before complex tasks
- Present comprehensive plans before executing
- Only exit plan mode after user approval

### Core Rules - DO NOT VIOLATE
- **NEVER create mock data or simplified components** unless explicitly told
- **NEVER replace existing complex components** - always fix the actual problem
- **ALWAYS work with the existing codebase** - no simplified alternatives
- **ALWAYS find and fix the root cause** - no workarounds
- Double check work for breaking changes, make frequent backups

### Memory & Documentation
- **Obsidian Vault**: `/Users/djm/claude-projects/claude-vault` 
- **Serena Memories**: Use `mcp__serena__read_memory` for quick context
- **Review CLAUDE.md** every 3 weeks for guideline adherence

## 🧭 QUICK NAVIGATION

### 📚 Essential Documentation
| Topic | Location | Quick Memory |
|-------|----------|--------------|
| Email System | [[KB-Email-System-Complete]] | `email-system-active` |
| Link Ingestion | [[KB-Link-Ingestion-Complete-Guide]] | `tool-selection-quick` |
| Development/TDD | [[KB-Development-Guidelines-TDD]] | `development-mode-settings` |
| Quality Standards | [[KB-Quality-Standards-Workspace]] | `quality-gates-active` |
| MCP Servers | [[KB-MCP-Server-Reference]] | - |
| Critical Paths | - | `critical-paths` |

### 🚀 Quick Commands
```bash
# Email to David
python /Users/djm/claude-projects/claude-email-api.py

# Quality check
python quality_scoring_rubric.py output.txt

# Workspace cleanup  
python tools/core/workspace-cleanup.py

# Link ingestion (choose one)
python complete-link-ingestion-tool.py URL      # 25 pages
python deepwiki-comprehensive-ingestion.py URL   # 150 pages
python ultra-comprehensive-ingestion.py URL      # 500 pages

# FZF productivity shortcuts (after installing fzf)
CTRL-T  # Fuzzy file search
CTRL-R  # Fuzzy command history
fo      # Fuzzy open vault notes (custom function)
ft      # Fuzzy run tools (custom function)
```

## 📧 Email Quick Reference
- **ALWAYS send to**: thedavidmurray@gmail.com
- **Use script**: `/Users/djm/claude-projects/claude-email-api.py`
- **NEVER use**: MCP Gmail tools (unreliable)
- **Quality gate**: 60+ score required
- **Full guide**: [[KB-Email-System-Complete]]

## 🔧 Development Quick Reference
- **TDD is NON-NEGOTIABLE** - Test first, always
- **No `any` types** - Use `unknown` instead
- **Immutable data only** - No mutations
- **TypeScript strict mode** - Always enabled
- **Full guide**: [[KB-Development-Guidelines-TDD]]

## 🎯 Task-Specific Loading

Load relevant context based on your task:

### For Email Tasks
1. Read memory: `mcp__serena__read_memory email-system-active`
2. If needed: [[KB-Email-System-Complete]]

### For Link Analysis
1. Read memory: `mcp__serena__read_memory tool-selection-quick`
2. If needed: [[KB-Link-Ingestion-Complete-Guide]]

### For Coding
1. Read memory: `mcp__serena__read_memory development-mode-settings`
2. If needed: [[KB-Development-Guidelines-TDD]]

### For Quality/Organization
1. Read memory: `mcp__serena__read_memory quality-gates-active`
2. If needed: [[KB-Quality-Standards-Workspace]]

### For Emergencies
1. Read memory: `mcp__serena__read_memory critical-paths`
2. Check: [[Config-Claude-MCP-Configuration]]

## 🏗️ Vault Structure Reference
```
claude-vault/
├── 01-Sessions/YYYY-MM/     # Debugging sessions
├── 03-Knowledge-Base/       # Reusable knowledge
│   ├── Tools/              # Tool documentation
│   └── Patterns/           # Code patterns
├── 05-Solutions/           # Problem solutions
└── 06-Config/              # Configurations
```

## 🔄 Workflow Triggers

### Always Create Obsidian Notes When:
1. Debugging complex issues (>15 min)
2. Learning new patterns
3. Making architectural decisions
4. Solving recurring problems
5. Finding non-obvious solutions

### Always Write Serena Memory When:
1. Discovering reusable patterns
2. Establishing new conventions
3. Creating project-specific rules
4. Documenting critical procedures

## ⚡ Agent Management
- Spin up sub-agents in parallel for research/analysis
- Use concurrent workflows to maximize efficiency
- Coordinate outputs for comprehensive solutions

## 🛠️ MCP Server Status
- **Active**: GitHub, Filesystem, Fetch, Git, Chroma, Playwright, Time, Serena, Figma, Context7, Blender
- **Unreliable**: Gmail (use direct API instead)
- **Config**: `/Users/djm/claude-projects/claude-mcp-config.json`
- **Full reference**: [[KB-MCP-Server-Reference]]

## 📋 Pre-Flight Checklist
Before starting any task:
- [ ] Check if plan mode needed (complex = yes)
- [ ] Load relevant memory/documentation
- [ ] Verify tools are appropriate
- [ ] Confirm quality gates understood
- [ ] Review critical rules above

## 🚦 Important Notes
- Frequently commit changes with descriptive messages
- Always prefer editing existing files over creating new ones
- Run linting and tests after code changes
- Use quality scoring before sending any analysis email
- Maintain workspace organization standards

---

**This is your navigation hub. For any detailed information, follow the links or load the memories. Keep this file under 10KB for optimal performance.**