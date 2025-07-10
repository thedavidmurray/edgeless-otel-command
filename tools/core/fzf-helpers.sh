#!/bin/bash
# FZF Helper Functions for Claude Projects Workflow
# Source this file in your ~/.zshrc or ~/.bashrc

# Fuzzy find and open vault note
fo() {
  local vault="/Users/djm/claude-projects/claude-vault"
  cd "$vault"
  local file=$(find . -name "*.md" | fzf \
    --height=80% \
    --layout=reverse \
    --info=inline \
    --border \
    --preview 'head -100 {}' \
    --preview-window=right:60%:wrap \
    --bind='ctrl-/:toggle-preview' \
    --header='📝 Select Obsidian Note (CTRL-/ to toggle preview)')
  [ -n "$file" ] && ${EDITOR:-vim} "$file"
  cd - > /dev/null
}

# Fuzzy find and run Python tool
ft() {
  local tools="/Users/djm/claude-projects/tools"
  local tool=$(find "$tools" -name "*.py" -not -path "*/\.*" | fzf \
    --height=80% \
    --layout=reverse \
    --info=inline \
    --border \
    --preview 'echo "📄 FILE: {}" && echo "" && head -50 {} && echo -e "\n---\n🔧 USAGE:" && grep -A5 -E "(usage:|Usage:|USAGE:)" {} 2>/dev/null || echo "No usage info found"' \
    --preview-window=right:60%:wrap \
    --header='🐍 Select Python Tool')
  if [ -n "$tool" ]; then
    echo "Selected: $tool"
    echo "Enter arguments (or press Enter for none):"
    read -r args
    if [ -n "$args" ]; then
      python "$tool" $args
    else
      python "$tool"
    fi
  fi
}

# Fuzzy search Serena memories
fm() {
  local memory_dir="/Users/djm/claude-projects/.serena/memories"
  if [ ! -d "$memory_dir" ]; then
    echo "Serena memories directory not found: $memory_dir"
    return 1
  fi
  local memory=$(find "$memory_dir" -type f | fzf \
    --height=80% \
    --layout=reverse \
    --info=inline \
    --border \
    --preview 'echo "🧠 MEMORY: {}" && echo "" && cat {}' \
    --preview-window=right:70%:wrap \
    --header='🧠 Select Serena Memory')
  [ -n "$memory" ] && ${EDITOR:-cat} "$memory"
}

# Fuzzy quality check emails
fq() {
  local file=$(find . -name "*email*.txt" -o -name "*email*.md" 2>/dev/null | fzf \
    --height=80% \
    --layout=reverse \
    --info=inline \
    --border \
    --preview 'echo "📧 QUALITY CHECK: {}" && echo "" && (python /Users/djm/claude-projects/quality_scoring_rubric.py {} 2>&1 | head -50 || echo "Unable to score") && echo -e "\n---\n📄 CONTENT:" && head -50 {}' \
    --preview-window=right:70%:wrap \
    --header='📧 Select Email to Quality Check')
  if [ -n "$file" ]; then
    echo "Running quality check on: $file"
    python /Users/djm/claude-projects/quality_scoring_rubric.py "$file"
  fi
}

# Fuzzy workspace cleanup preview
fc() {
  echo "🧹 Analyzing workspace for cleanup..."
  local cleanup_script="/Users/djm/claude-projects/tools/core/workspace-cleanup.py"
  if [ ! -f "$cleanup_script" ]; then
    echo "Workspace cleanup script not found: $cleanup_script"
    return 1
  fi
  
  echo "Files that would be cleaned up:"
  python "$cleanup_script" --dry-run 2>&1 | fzf \
    --height=80% \
    --layout=reverse \
    --info=inline \
    --border \
    --header='🧹 Preview Files for Cleanup (ESC to cancel)'
  
  echo ""
  read -p "Run actual cleanup? (y/n) " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    python "$cleanup_script"
  else
    echo "Cleanup cancelled."
  fi
}

# Fuzzy git operations
fgit() {
  local action=$(echo -e "status\nlog\nbranch\ncheckout\nadd\ncommit\ndiff" | fzf \
    --height=40% \
    --layout=reverse \
    --info=inline \
    --border \
    --header='🔧 Select Git Operation')
  
  case "$action" in
    "status")
      git status
      ;;
    "log")
      git log --oneline --color=always | fzf \
        --ansi \
        --height=80% \
        --layout=reverse \
        --preview 'git show --color=always {1}' \
        --preview-window=right:60%:wrap
      ;;
    "branch")
      git branch -a --color=always | fzf \
        --ansi \
        --height=60% \
        --layout=reverse \
        --preview 'git log --oneline --color=always {1}' | \
        sed 's/^[* ]*//' | \
        xargs git checkout
      ;;
    "add")
      git status -s | fzf -m \
        --height=80% \
        --layout=reverse \
        --preview 'git diff --color=always {2}' | \
        awk '{print $2}' | \
        xargs git add
      ;;
    "diff")
      git diff --color=always | less -R
      ;;
    *)
      echo "Action cancelled"
      ;;
  esac
}

# Fuzzy find KB articles
fkb() {
  local kb_dir="/Users/djm/claude-projects/claude-vault/03-Knowledge-Base"
  cd "$kb_dir"
  local file=$(find . -name "KB-*.md" | fzf \
    --height=80% \
    --layout=reverse \
    --info=inline \
    --border \
    --preview 'head -150 {}' \
    --preview-window=right:60%:wrap \
    --header='📚 Select Knowledge Base Article')
  [ -n "$file" ] && ${EDITOR:-vim} "$file"
  cd - > /dev/null
}

# Fuzzy session notes by date
fs() {
  local sessions_dir="/Users/djm/claude-projects/claude-vault/01-Sessions"
  cd "$sessions_dir"
  local file=$(find . -name "Session-*.md" | sort -r | fzf \
    --height=80% \
    --layout=reverse \
    --info=inline \
    --border \
    --preview 'head -150 {}' \
    --preview-window=right:60%:wrap \
    --header='📅 Select Session Note')
  [ -n "$file" ] && ${EDITOR:-vim} "$file"
  cd - > /dev/null
}

# Fuzzy find and run ingestion tool with URL
fi() {
  local ingestion_dir="/Users/djm/claude-projects/tools/ingestion"
  local tool=$(find "$ingestion_dir" -name "*.py" | fzf \
    --height=60% \
    --layout=reverse \
    --info=inline \
    --border \
    --preview 'echo "🔗 INGESTION TOOL: {}" && echo "" && head -30 {}' \
    --header='🔗 Select Ingestion Tool')
  
  if [ -n "$tool" ]; then
    echo "Selected: $(basename $tool)"
    echo "Enter URL to ingest:"
    read -r url
    if [ -n "$url" ]; then
      python "$tool" "$url"
    else
      echo "No URL provided. Cancelled."
    fi
  fi
}

# Show all FZF helper commands
fhelp() {
  echo "🚀 FZF Helper Commands:"
  echo ""
  echo "  fo    - Fuzzy Open vault notes"
  echo "  ft    - Fuzzy run Tools"
  echo "  fm    - Fuzzy search Memories"
  echo "  fq    - Fuzzy Quality check"
  echo "  fc    - Fuzzy Cleanup preview"
  echo "  fgit  - Fuzzy Git operations"
  echo "  fkb   - Fuzzy KB articles"
  echo "  fs    - Fuzzy Session notes"
  echo "  fi    - Fuzzy Ingestion tools"
  echo "  fhelp - Show this help"
  echo ""
  echo "📌 Global Shortcuts:"
  echo "  CTRL-T - Fuzzy file search"
  echo "  CTRL-R - Fuzzy command history"
  echo "  ALT-C  - Fuzzy directory change"
  echo ""
  echo "🔍 Search Operators:"
  echo "  ^prefix  - Items starting with prefix"
  echo "  suffix$  - Items ending with suffix"
  echo "  'exact   - Exact match"
  echo "  !inverse - Items not matching"
}

# Print message when sourced
echo "✅ FZF helpers loaded. Type 'fhelp' for available commands."