# VPN Bot for 3x-ui

Telegram-бот на `Python 3.11+` для автоматической выдачи и показа персональных VPN-конфигов через `3x-ui`.

## Что умеет

- при первом `/start` создаёт пользователя в БД;
- если клиент уже есть в `3x-ui`, импортирует его в БД;
- если клиента ещё нет, создаёт клиентский аккаунт в `3x-ui`;
- сохраняет `client_id`, `email`, `uuid`, `inbound_id`, `config_url`, срок действия;
- при повторном входе показывает уже существующий конфиг;
- даёт админ-команды для поиска, отключения, продления и пересборки конфига.

## Структура

```text
app/
  bot/
  core/
  db/
  services/
alembic/
Dockerfile
docker-compose.yml
.env.example
README.md
```

## Подготовка `.env`

1. Скопируй пример:

```bash
cp .env.example .env
```

2. Заполни обязательные переменные:

```env
BOT_TOKEN=
ADMIN_IDS=
DATABASE_URL=postgresql+asyncpg://vpn:vpn@db:5432/vpn_bot

XUI_BASE_URL=https://your-host:2053/your-web-base-path
XUI_USERNAME=
XUI_PASSWORD=
XUI_INBOUND_ID=

VPN_HOST=
VPN_PORT=
VPN_SNI=
VPN_HOST_HEADER=
VPN_PUBLIC_KEY=
VPN_SHORT_ID=
```

Важно:

- `XUI_BASE_URL` указывается уже вместе с `WebBasePath`, если он включён в панели.
- реальные секреты не должны попадать в git.

### Пример для VLESS + WebSocket + TLS

```env
XUI_INBOUND_ID=2
VPN_HOST=213.165.40.42
VPN_PORT=8443
VPN_PROTOCOL=vless
VPN_SECURITY=tls
VPN_TYPE=ws
VPN_PATH=/neko
VPN_SNI=
VPN_HOST_HEADER=
VPN_FLOW=
VPN_PUBLIC_KEY=
VPN_SHORT_ID=
VPN_FINGERPRINT=
VPN_ALPN=
```

При таких параметрах ссылка будет собираться так:

```text
vless://UUID@213.165.40.42:8443?type=ws&security=tls&path=%2Fneko#vpn
```

Пустые параметры `sni`, `host`, `fp`, `alpn`, `flow`, `pbk`, `sid` в ссылку не добавляются.

## Запуск через Docker Compose

```bash
docker compose up --build -d
```

Логи:

```bash
docker compose logs -f bot
```

## Применение миграций

Если контейнер уже поднят:

```bash
docker compose exec bot alembic upgrade head
```

Локально без Docker:

```bash
alembic upgrade head
```

## Локальный запуск

1. Установи зависимости:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install .
```

2. Запусти миграции:

```bash
alembic upgrade head
```

3. Запусти бота:

```bash
python -m app.main
```

## Проверка подключения к 3x-ui

```bash
python -m app.main --check-xui
```

Ожидаемый результат:

```text
3x-ui connection OK
```

## Админ-команды

- `/admin`
- `/admin_find <telegram_id>`
- `/admin_import <telegram_id>`
- `/admin_import_email <telegram_id> <email>`
- `/admin_disable <telegram_id>`
- `/admin_extend <telegram_id> <days>`
- `/admin_recreate <telegram_id>`

## Импорт существующих пользователей

Автоматический импорт при `/start` работает, если клиент в `3x-ui` уже имеет `email` в формате:

```text
tg-<telegram_id>
```

Пример:

```text
tg-5478201425
```

Если старые клиенты заведены с другими `email`, используй ручную привязку:

```bash
/admin_import_email 5478201425 old-client-email
```

Если старый клиент уже использует формат `tg-<telegram_id>`, достаточно:

```bash
/admin_import 5478201425
```

## Деплой на Ubuntu-сервер

1. Установи Docker и Docker Compose plugin.
2. Скопируй проект на сервер.
3. Создай `.env`.
4. Запусти:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

5. Проверь:

```bash
docker compose ps
docker compose logs -f bot
```

## CI/CD через GitHub Actions

В проекте уже добавлены workflow:

- `.github/workflows/ci.yml`:
  проверка Python-кода и сборка Docker image
- `.github/workflows/deploy.yml`:
  копирование проекта на сервер и локальная сборка через Docker Compose

### Что нужно для работы deploy workflow

1. Хранить код в GitHub-репозитории.
2. Добавить в GitHub Secrets:

```text
SSH_HOST
SSH_USER
SSH_PASSWORD
SSH_PORT
```

3. На сервере должен существовать каталог:

```text
/opt/vpn_bot
```

4. В `/opt/vpn_bot/.env` должен лежать production `.env`.

### Как работает деплой

- GitHub Actions копирует проект на сервер в `/opt/vpn_bot`
- на сервере выполняется локальная сборка и запуск:

```bash
/opt/vpn_bot/scripts/deploy.sh
```

Фактически deploy-скрипт запускает:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### Первый запуск на сервере

После первого копирования проекта создай `.env` в `/opt/vpn_bot`, затем можно запускать деплой либо вручную, либо через GitHub Actions.

## Замечания по 3x-ui

- бот использует cookie-сессию после логина в `3x-ui`;
- для повторных запросов логин не выполняется каждый раз;
- ошибки панели пробрасываются как отдельные исключения;
- для продления используется API `updateClient`, поэтому перед продакшен-запуском стоит проверить совместимость именно с твоей версией `3x-ui`.
