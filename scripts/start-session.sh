#!/usr/bin/env bash
set -euo pipefail

echo ""
echo "═══════════════════════════════════════════════"
echo "     🎬 РИТУАЛ НАЧАЛА СЕССИИ — GSM"
echo "═══════════════════════════════════════════════"
echo ""

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "[1/5] Git status (последние 5 коммитов)"
echo "───────────────────────────────────────────────"
if git rev-parse --is-inside-work-tree 2>/dev/null; then
    git log --oneline -5 2>/dev/null || echo "  (нет коммитов)"
    echo ""
    echo "  Неотслеживаемые / изменённые файлы:"
    git status -s 2>/dev/null || echo "  (чисто)"
else
    echo "  (git-репозиторий не инициализирован)"
fi

echo ""
echo "[2/5] Docker Compose"
echo "───────────────────────────────────────────────"
if [ -f docker-compose.yml ]; then
    docker compose ps 2>/dev/null || echo "  (контейнеры не запущены)"
else
    echo "  (docker-compose.yml не найден)"
fi

echo ""
echo "[3/5] Проверка структуры проекта"
echo "───────────────────────────────────────────────"
echo "  backend/app/    $(find backend/app -name '*.py' 2>/dev/null | wc -l) .py файлов"
echo "  backend/docker/ $(find backend/docker -name '*.sql' 2>/dev/null | wc -l) .sql файлов"
echo "  context/        $(find context -name '*.md' 2>/dev/null | wc -l) .md файлов"
echo "  scripts/        $(find scripts -name '*.sh' 2>/dev/null | wc -l) .sh файлов"

echo ""
echo "[4/5] Python syntax check"
echo "───────────────────────────────────────────────"
if [ -d backend/app ]; then
    errors=0
    while IFS= read -r -d '' file; do
        if ! python3 -m py_compile "$file" 2>/dev/null; then
            echo "  ❌ $file"
            errors=$((errors + 1))
        fi
    done < <(find backend/app -name '*.py' -print0)
    if [ "$errors" -eq 0 ]; then
        echo "  ✅ Все .py файлы валидны"
    else
        echo "  ⚠️  Найдено ошибок: $errors"
    fi
fi

echo ""
echo "[5/5] Последний SNAPSHOT"
echo "───────────────────────────────────────────────"
if [ -f context/SNAPSHOT.md ]; then
    grep -m 3 "^##\|^Status\|^Статус" context/SNAPSHOT.md || true
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  ✅ Ритуал завершён. Доклад готов."
echo "═══════════════════════════════════════════════"
echo ""
