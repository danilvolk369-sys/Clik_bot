#!/usr/bin/env bash
# 🚀 Railway Deploy Checklist Script

echo "╔════════════════════════════════════════════════════╗"
echo "║  КликТохн Railroad Checklist               ✅     ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

CHECKS=0
PASS=0

# Функция проверки файла
check_file() {
    CHECKS=$((CHECKS + 1))
    if [ -f "$1" ]; then
        echo "✅ $1"
        PASS=$((PASS + 1))
    else
        echo "❌ $1 - НЕ НАЙДЕН"
    fi
}

# Функция проверки содержимого
check_content() {
    CHECKS=$((CHECKS + 1))
    if grep -q "$2" "$1" 2>/dev/null; then
        echo "✅ $1 содержит: $2"
        PASS=$((PASS + 1))
    else
        echo "❌ $1 НЕ содержит: $2"
    fi
}

echo "📁 Проверка файлов:"
check_file "config.py"
check_file "main.py"
check_file "requirements.txt"
check_file ".env.example"
check_file "railway.json"
check_file "Procfile"
check_file "runtime.txt"
check_file ".gitignore"
check_file "RAILWAY_SETUP.md"

echo ""
echo "📄 Проверка содержимого:"
check_content "config.py" "PORT = int(os.getenv"
check_content "requirements.txt" "aiohttp"
check_content ".env.example" "BOT_TOKEN"
check_content "railway.json" "healthcheckPort"
check_content "runtime.txt" "python-3.11"

echo ""
echo "════════════════════════════════════════════════════"
echo "Результат: $PASS / $CHECKS ✓"
echo "════════════════════════════════════════════════════"

if [ "$PASS" -eq "$CHECKS" ]; then
    echo ""
    echo "✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!"
    echo ""
    echo "Следующие шаги:"
    echo "1. Экспортируйте .env в Railway Variables"
    echo "2. Создайте Volume /data для БД"
    echo "3. Выполните: git push railway main"
    echo ""
    echo "📖 Подробнее: см. RAILWAY_SETUP.md"
else
    echo ""
    echo "⚠️  Некоторые проверки не прошли"
    echo "Нужно исправить ошибки перед развертыванием"
fi

echo ""
