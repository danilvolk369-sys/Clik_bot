# 🚀 Развертывание на Railway

## Что было подготовлено

✅ **config.py** — добавлены переменные PORT и RAILWAY_ENVIRONMENT  
✅ **requirements.txt** — добавлены зависимости (aiohttp)  
✅ **.env.example** — пример переменных окружения  
✅ **railway.json** — конфигурация Railway  
✅ **.gitignore** — правильная конфигурация для Git  

---

## Шаг 1: Подготовка Railway проекта

### 1.1 Создайте аккаунт и проект на Railway
- Перейдите на https://railway.app
- Создайте новый проект
- Выберите "Deploy from GitHub"

### 1.2 Свяжите репозиторий
```bash
git init
git add .
git commit -m "Initial commit"
git remote add railway <railway-git-url>
git push railway main
```

---

## Шаг 2: Установите переменные окружения на Railway

В Railway dashboard перейдите в **Variables** и добавьте:

| Переменная | Значение | Примечание |
|-----------|---------|-----------|
| `BOT_TOKEN` | `8507895212:AAG...` | Токен бота из @BotFather |
| `BOT_USERNAME` | `imopesbot` | Имя бота |
| `REFERRAL_BOT_USERNAME` | `imopesbot` | То же имя |
| `OWNER_ID` | `8275665893` | Ваш ID Telegram |
| `DB_NAME` | `/data/clicktohn.db` | **ВАЖНО:** /data/ для Volume! |
| `SBER_CARD` | `2202 2081 2341 5326...` | Карта для платежей (опционально) |
| `RAILWAY_ENVIRONMENT` | `production` | Среда |
| `PORT` | `8080` | Railway назначит автоматически |

---

## Шаг 3: Подготовьте Volume для базы данных

### 3.1 В Railway dashboard:
1. Перейдите в **Data** → **Volumes**
2. Создайте новый Volume: `clicktohn-db`
3. Смонтируйте его по пути `/data`

### 3.2 Загрузите seed-БД перед первым запуском:
```bash
# Скопируйте локальный clicktohn.db на Volume
# Railway предоставит инструкции в dashboard
```

---

## Шаг 4: Проверьте Procfile

```plaintext
worker: python main.py
```

Этот файл уже имеется в проекте.

---

## Шаг 5: Развернуть проект

### Вариант А: Через GitHub (рекомендуется)
1. Сделайте `git push railway main`
2. Railway автоматически подхватит изменения
3. Проверьте логи в Deployments

### Вариант Б: Через Railway CLI
```bash
npm install -g @railway/cli
railway login
railway up
```

---

## 📋 Чек-лист перед запуском

- [ ] BOT_TOKEN установлен на Railway
- [ ] OWNER_ID установлен
- [ ] DB_NAME указывает на `/data/clicktohn.db`
- [ ] Volume `/data` смонтирован
- [ ] Seed-БД загружена на Volume (если нужна инициализация)
- [ ] GitHub репозиторий синхронизирован с Railway

---

## 🔧 Обновление после изменений

```bash
git add .
git commit -m "Fix/feature description"
git push railway main
```

Railway автоматически перестартует приложение.

---

## 📊 Мониторинг

В Railway dashboard:
- **Deployments** — история развертываний
- **Logs** — логи приложения в реальном времени
- **Metrics** — CPU, память, сетевую статистику

---

## ❌ Если что-то не работает

1. **Проверьте логи**: Deployments → View Logs
2. **Убедитесь в переменных**: Variables завдала корректно
3. **Volume монтирован**: Data → Volumes → проверьте `/data`
4. **Python версия**: Railway использует Python 3.11+ (автоматически)

---

## 🔗 Полезные ссылки

- [Railway Docs](https://docs.railway.app/)
- [Railway Volumes](https://docs.railway.app/reference/volumes)
- [Railway Environment Variables](https://docs.railway.app/reference/variables)
