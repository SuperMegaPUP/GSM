#!/usr/bin/env bash
set -euo pipefail

echo ""
echo "═══════════════════════════════════════════════"
echo "     📝 РИТУАЛ КОНЦА СЕССИИ — GSM"
echo "═══════════════════════════════════════════════"
echo ""

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

SESSION_DATE=$(date +%Y-%m-%d_%H-%M)

# ==========================================
# 1. Python syntax check
# ==========================================
echo "[1/4] Проверка синтаксиса Python..."
errors=0
while IFS= read -r -d '' file; do
    if ! python3 -m py_compile "$file" 2>/dev/null; then
        echo "  ❌ $file"
        errors=$((errors + 1))
    fi
done < <(find backend/app -name '*.py' -print0 2>/dev/null || true)

if [ "$errors" -eq 0 ]; then
    echo "  ✅ Все .py файлы валидны"
else
    echo "  ⚠️  Найдено ошибок: $errors"
fi

# ==========================================
# 2. Обновление SNAPSHOT.md
# ==========================================
echo "[2/4] Обновление SNAPSHOT.md..."

SNAPSHOT_FILE="context/SNAPSHOT.md"

# Обновляем дату
sed -i "s/^\*\*Дата:\*\* .*$/**Дата:** $(date +%Y-%m-%d)/" "$SNAPSHOT_FILE" 2>/dev/null || true

# Обновляем дерево проекта
if command -v tree &>/dev/null; then
    tree_output=$(tree --charset=utf-8 -I '__pycache__|*.pyc|.git|.venv|node_modules' 2>/dev/null || true)
else
    tree_output=$(find . -not -path './.git/*' -not -path '*/__pycache__/*' -not -path '*/node_modules/*' -not -name '*.pyc' -not -name '.git' | head -80 2>/dev/null || true)
fi

# ==========================================
# 3. WORKLOG.md — добавляем запись
# ==========================================
echo "[3/4] Обновление WORKLOG.md..."

WORKLOG_FILE="context/WORKLOG.md"
TEMP_WORKLOG=$(mktemp)

{
    echo ""
    echo "---"
    echo ""
    echo "## Сессия от $SESSION_DATE"
    echo ""
    echo "**Что сделано:**
"
    echo "- *(автоматическая запись — требуется уточнение)*"
    echo ""
    echo "**Решения:**"
    echo "-"
    echo ""
    echo "**Следующий шаг:**"
    echo "-"
    echo ""
    cat "$WORKLOG_FILE"
} > "$TEMP_WORKLOG" 2>/dev/null || true

mv "$TEMP_WORKLOG" "$WORKLOG_FILE" 2>/dev/null || true

# ==========================================
# 4. Финальный git status
# ==========================================
echo "[4/4] Git status..."
if git rev-parse --is-inside-work-tree 2>/dev/null; then
    git status -s 2>/dev/null || true
    echo ""
    echo "  Чтобы закоммитить:"
    echo "    git add -A && git commit -m \"сессия: ...\" && git push origin main"
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  ✅ Документация обновлена."
echo "═══════════════════════════════════════════════"
echo ""
