#!/bin/bash

# Create a fresh, clean repository without history

echo "Creating clean repository..."

# 1. Save current state
mkdir -p /tmp/wdfwatch_clean
cp -r . /tmp/wdfwatch_clean/ 2>/dev/null

# 2. Remove git and sensitive files
cd /tmp/wdfwatch_clean
rm -rf .git
rm -rf web/.next
rm -rf .serena
rm -rf migration_package
rm -rf wdfwatch_*.tar.gz
rm -rf *.sql *.sql.gz

# 3. Initialize new repository
git init
git branch -M main
git add .
git commit -m "Initial commit: Clean WDFWatch repository

- Twitter bot for War, Divorce, or Federalism podcast
- Python pipeline with LLM integration
- Next.js web UI for management
- No sensitive data or build artifacts"

# 4. Add remote and push
git remote add origin https://github.com/wyatt727/WDFWatch.git
echo "Ready to push. Run: git push -u origin main --force"

echo "Files in clean repo:"
git ls-files | wc -l
echo "Repository size:"
du -sh .git
