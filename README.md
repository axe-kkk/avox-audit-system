# AVOX Revenue Engine Audit

Сервис принимает анкету (10 вопросов + контакты), анализирует сайт клиента, считает **четыре столба** скоринга, генерирует **PDF-отчёт** и шлёт уведомления в **Telegram** (старт аудита и готовый отчёт с файлом).

---

## 1. Заполнение `.env`

Скопируйте пример и отредактируйте файл **`.env`** в корне проекта (рядом с `docker-compose.yml`).

```bash
cp .env.example .env
```

| Переменная | Назначение | Пример / комментарий |
|------------|------------|----------------------|
| **`POSTGRES_USER`** / **`POSTGRES_PASSWORD`** / **`POSTGRES_DB`** | Учётка БД для образа `db` в Docker Compose. | Пароль без символов `@ : / ? # &` (ломают URL). |
| **`DATABASE_URL`** | PostgreSQL **asyncpg** для локального API без Docker-стека. | `postgresql+asyncpg://postgres:postgres@localhost:5432/avox_revenue_gaps` |
| **`DEBUG`** | Лог SQL в консоль. | `false` |
| **`API_PREFIX`** | Префикс REST API. | `/api/v1` |
| **`ALLOWED_ORIGINS`** | CORS, через запятую без пробелов. | `http://localhost:3000` |
| **`OPENAI_API_KEY`** | Ключ OpenAI для LLM (аудит + часть enrichment). | `sk-...` |
| **`LLM_MODEL`** | Модель для «тяжёлых» текстов. | `gpt-4o` |
| **`LLM_MODEL_MINI`** | Модель для классификаций / выбора ссылок. | `gpt-4o-mini` |
| **`TELEGRAM_BOT_TOKEN`** | Токен бота от @BotFather. | опционально; без него уведомления не уходят |
| **`TELEGRAM_CHAT_ID`** | ID чата/канала куда слать сообщения. | опционально |
| **`PDF_OUTPUT_DIR`** | Каталог для PDF (локально и в Docker volume). | `storage/pdfs` |
| **`REDIS_URL`** | Redis для Celery (локально). | `redis://localhost:6379/0` |
| **`CELERY_BROKER_URL`** | Брокер задач. | `redis://localhost:6379/0` |
| **`CELERY_RESULT_BACKEND`** | Хранилище результатов Celery. | `redis://localhost:6379/1` |

**Docker Compose:** для `api`, `worker`, `migrate` строка **`DATABASE_URL` собирается из `POSTGRES_*`** в `docker-compose.yml` (хост `db` внутри сети). Остальное из `.env`. Подробности деплоя на сервер — **`DEPLOY.md`**.

**Важно:** не коммитьте `.env` с реальными ключами в публичный репозиторий.

---

## 2. Локальный запуск

### Требования

- Python **3.12+**
- **PostgreSQL** 15+
- **Redis** 7+
- **Chromium** через Playwright (`playwright install chromium`)

### Шаги

1. Создать БД, например: `createdb avox_revenue_gaps` (или через GUI).
2. Виртуальное окружение и зависимости:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

3. Настроить **`.env`** (см. раздел 1). Для локали `DATABASE_URL` указывает на `localhost`.
4. Миграции:

```bash
alembic upgrade head
```

5. Запустить **два процесса** (в двух терминалах):

**Терминал A — API:**

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Терминал B — Celery worker** (обработка пайплайна после POST заявки):

```bash
celery -A app.celery_app worker --loglevel=info --pool=solo
```

На Windows для Celery часто используют `--pool=solo`, чтобы избежать проблем с fork.

- Документация OpenAPI: **http://localhost:8000/docs**
- Проверка живости: **GET** `http://localhost:8000/health` → `{"status":"ok"}`

---

## 3. Запуск в Docker (сервер)

`docker-compose.yml` рассчитан на **продакшен**: **Caddy** на **80/443** (TLS), **PostgreSQL** и **Redis** без проброса портов на хост, **API** снаружи только через Caddy.

Из корня проекта:

```bash
cp .env.example .env
# на сервере: POSTGRES_PASSWORD, ALLOWED_ORIGINS (HTTPS), Redis → redis://redis:6379/...
# при необходимости отредактируйте Caddyfile (домен)

docker compose up -d --build
```

Снаружи приложение открывается по **HTTPS** с хоста из **`Caddyfile`** (по умолчанию `avox-development.pp.ua`), форма: **`/`**. Пошагово — **`DEPLOY.md`**.

Для **разработки без полного Docker-стека** удобнее раздел **2** (uvicorn + Celery на машине, своя БД/Redis).

### За что отвечает каждый контейнер

| Сервис | Образ / сборка | Роль |
|--------|----------------|------|
| **`db`** | `postgres:16-alpine` | БД, том `pgdata`, порт **не** проброшен наружу. |
| **`redis`** | `redis:7-alpine` | Очередь Celery, порт **не** проброшен наружу. |
| **`migrate`** | сборка из `Dockerfile` | Одноразово: `alembic upgrade head`. |
| **`api`** | тот же образ | FastAPI внутри сети compose, том **`pdf_storage`**. |
| **`worker`**, **`worker2`** | тот же образ | Celery workers (пайплайн после POST заявки). |
| **`caddy`** | `caddy:2-alpine` | TLS и прокси на **api:8000** (`Caddyfile` в корне). |

Том **`pdf_storage`** общий для `api` и воркеров.

Остановка: `docker compose down`. Полный сброс БД: `docker compose down -v`.

---

## 4. Допустимые значения анкеты (JSON для API)

В теле **POST** `/api/v1/submissions` поля должны совпадать с **строковыми значениями enum** ниже (как в Python `Enum.value`).

### Контакты

| Поле | Тип | Обязательно |
|------|-----|:-------------:|
| `full_name` | строка | да |
| `work_email` | email | да |

### Q1 — CRM (`crm`)

| Значение JSON | Смысл |
|---------------|--------|
| `hubspot` | HubSpot |
| `salesforce` | Salesforce |
| `zoho` | Zoho |
| `odoo` | Odoo |
| `other` | Другая CRM → обязательно заполнить **`crm_other`** (текст) |
| `no_crm` | Нет CRM / другие инструменты |

### Q2 — Сайт

| Поле | Тип |
|------|-----|
| `company_url` | строка (URL компании) |

### Q3 — Размер команды (`team_size`)

| Значение | Диапазон |
|----------|----------|
| `<10` | до 10 |
| `10-20` | 10–20 |
| `20-50` | 20–50 |
| `50+` | 50+ |

### Q4 — Лиды в месяц (`monthly_leads`)

| Значение | Смысл |
|----------|--------|
| `<100` | до 100 |
| `100-500` | 100–500 |
| `500-2000` | 500–2 000 |
| `2000+` | 2 000+ |

### Q5 — Обработка лидов (`lead_handling`)

| Значение | Смысл |
|----------|--------|
| `all_on_time` | Успеваем обработать все вовремя |
| `probably_miss` | Вероятно часть теряется |
| `definitely_lose` | Точно теряем лиды |

### Q6 — Каналы (`channels_used`)

Массив строк; **минимум один** элемент. Только из набора:

| Значение | Смысл |
|----------|--------|
| `phone` | Телефон |
| `email` | Email |
| `website_chat` | Чат на сайте |
| `messenger_whatsapp_viber` | Мессенджеры / WhatsApp / Viber |
| `social_dms` | Соцсети (DM) |
| `other` | Другое |

### Q7 — Единый вид клиента (`unified_view`)

| Значение | Смысл |
|----------|--------|
| `yes` | Да |
| `partially` | Частично |
| `no` | Нет |

### Q8 — Upsell / cross-sell (`upsell_crosssell`)

| Значение | Смысл |
|----------|--------|
| `yes_automated` | Да, автоматизировано |
| `manual_only` | Только вручную |
| `no` | Нет |

### Q9 — Отток (`churn_detection`)

| Значение | Смысл |
|----------|--------|
| `proactive` | Проактивная система |
| `manual` | Вручную |
| `we_dont` | Не отслеживаем |

### Q10 — Фрустрации (`biggest_frustrations`)

Массив строк (можно несколько). Только из набора:

| Значение | Смысл |
|----------|--------|
| `revenue_doesnt_scale` | Выручка не масштабируется |
| `too_many_tools_no_picture` | Много инструментов, нет единой картины |
| `dont_know_which_customers` | Непонятно, на каких клиентах фокус |
| `no_upsell_retention_system` | Нет upsell / удержания |
| `cant_measure_whats_working` | Нельзя измерить, что работает |

---

## 5. Типичные ошибки и сбои

| Симптом | Возможная причина |
|---------|-------------------|
| **422 Unprocessable Entity** на POST | Неверные enum-строки, пустой `channels_used`, для `crm=other` нет `crm_other`, недопустимый email. |
| **404** на GET audit / pdf | Заявка не существует или пайплайн ещё не создал `Audit` / PDF. |
| **`status`: `failed`**, `error_message` в заявке | Исключение в worker (сеть, LLM, Playwright, WeasyPrint и т.д.). Celery может **повторить** задачу один раз с задержкой. |
| Миграции в Docker падают | В БД осталась старая ревизия Alembic, а файлов миграции нет — см. `docker compose down -v` + зафиксированные файлы в `alembic/versions/`. |
| Нет сообщений в Telegram | Пустые `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — шаги просто пропускаются. |
| PDF не отдаётся из API в Docker | `worker` и `api` должны видеть **один том** `pdf_storage`; путь в БД должен совпадать с тем, что видит процесс `api`. |
| OpenAI errors | Неверный ключ, лимиты, модель недоступна — падает генерация текста аудита (частично есть fallback в коде). |

---

## 6. Маршруты API и примеры

Базовый префикс: **`{API_PREFIX}`** по умолчанию **`/api/v1`**.

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/health` | Healthcheck (без префикса v1). |
| POST | `/api/v1/submissions` | Создать заявку и **поставить пайплайн в очередь** Celery. |
| GET | `/api/v1/submissions` | Список заявок с пагинацией. |
| GET | `/api/v1/submissions/{id}` | Одна заявка по id. |
| GET | `/api/v1/audits/{submission_id}` | Аудит (скоры, JSON контента, пути к PDF). |
| GET | `/api/v1/audits/{submission_id}/pdf` | Скачать PDF (когда готов). |

Параметры списка заявок:

- `page` (default 1)
- `per_page` (1–50, default 10)
- `status` — фильтр: `pending`, `enriching`, `scoring`, `generating`, `completed`, `failed`

### Пример: создать заявку

```bash
curl -s -X POST "http://localhost:8000/api/v1/submissions" ^
  -H "Content-Type: application/json" ^
  -d "{\"full_name\":\"Test User\",\"work_email\":\"user@example.com\",\"crm\":\"hubspot\",\"company_url\":\"https://example.com\",\"team_size\":\"20-50\",\"monthly_leads\":\"100-500\",\"lead_handling\":\"probably_miss\",\"channels_used\":[\"phone\",\"email\",\"website_chat\"],\"unified_view\":\"partially\",\"upsell_crosssell\":\"manual_only\",\"churn_detection\":\"manual\",\"biggest_frustrations\":[\"cant_measure_whats_working\"]}"
```

(В PowerShell удобнее сохранить JSON в файл и передать `-d @body.json`.)

### Пример: статус и аудит

```bash
curl -s "http://localhost:8000/api/v1/submissions/1"
curl -s "http://localhost:8000/api/v1/audits/1"
curl -s -o report.pdf "http://localhost:8000/api/v1/audits/1/pdf"
```

Интерактивно: **http://localhost:8000/docs** (Swagger).

---

## 7. Логика аудита (пайплайн)

После успешного **POST** `/submissions`:

1. **Запись в БД**, статус `pending` → сразу **`enriching`**.
2. **Telegram (если настроен):** сообщение «аудит запущен» — сайт, контакт, **номер заявки**.
3. **Website enrichment** (воркер): обход/выбор страниц, Playwright, Wappalyzer, парсинг GTM, LLM-анализ → JSON (`detected_tools`, `site_features`, `signals_count`, трафик и т.д.).
4. **Scoring** — четыре столба + `total_score`, `score_interpretation`, флаги по сигналам.
5. **AI audit** — LLM формирует **фактологичные** тексты (без советов): сводка, находки, блоки по столбам, снимок баллов в поле с legacy-именем `estimated_revenue_opportunity`.
6. **PDF** — брендированный отчёт: скоры, таблица анкеты, разбивка модели, инвентарь технологий, структурированные наблюдения.
7. **Сохранение `Audit`** в БД.
8. **Telegram:** итоговое сообщение со скорами и PDF-файлом.

При ошибке: статус заявки **`failed`**, текст ошибки усечён в `error_message`. Celery может повторить задачу.

---

## 8. Логика расчёта оценки (скоринг)

**Revenue Engine Score** = **среднее арифметическое** четырёх столбов, каждый столб **0–100** (с округлением итога до 0.1).

В ответе API столбы лежат в полях (исторические имена):

| Ключ JSON | Смысл в текущей модели |
|-----------|-------------------------|
| `cdp` | **Данные и оркестрация** (CRM, каналы, единый вид + стек на сайте + согласованность) |
| `ai_agent` | **Лид-движок** (обработка лидов, нагрузка vs команда, поверхность захвата на сайте) |
| `recommendation` | **Рост и удержание** (upsell/churn по форме, монетизация на сайте, фрустрации Q10) |
| `analytics` | **Аналитика и атрибуция** (уверенность в измерениях по форме, трекинг и продвинутые сигналы на сайте) |

У каждого столба **три подпоказателя** (в `*_score_details`): каждый нормирован **0–100**, итог столба — **взвешенное среднее** трёх блоков (веса свои у каждого столба).

### Общие правила

- **`signals_count` > 0** считается «сайт просканирован с сигналами»; тогда блоки «сайт» используют реальные детекты (CRM, аналитика, чат, тарифы и т.д.).
- Если **сигналов нет**, «сайт»-компоненты **не нули**, а **ограниченно выводятся из анкеты** (честный режим «мало данных с сайта»).
- **Семейства каналов на сайте** для сверки с Q6 считаются **без** отдельного балла за каждую соцсеть: чат, мессенджеры, бронь, телефон, email, «есть соцсети» — отдельные **семейства**.

### Столб 1 (`cdp`)

| Блок | Вес (порядок) | Содержание |
|------|---------------|------------|
| Форма | 44% | CRM (Q1), unified view (Q7), «ширина» каналов Q6 (нормализованная таблица). |
| Сайт / вывод | 36% | Баллы за CRM/CDP/web analytics/behavior/MA на сайте **или** усечённый вывод из CRM+unified при отсутствии скана. |
| Согласованность | 20% | Штраф, если на сайте **больше семейств каналов**, чем выбрано в Q6; Q10 `too_many_tools_no_picture`; unified=yes при отсутствии CRM/CDP на публичных страницах. |

### Столб 2 (`ai_agent`)

| Блок | Вес | Содержание |
|------|-----|------------|
| Форма | 46% | Q5 (обработка лидов) с учётом Q4; **соответствие** размера команды (Q3) и объёма лидов (Q4) через коэффициент «лидов на условную команду». |
| Сайт | 40% | Чат, боты, формы, телефон, бронь, мессенджеры, MA, база знаний — **или** fallback из формы при пустом скане. |
| Контекст процесса | 14% | Штраф за `no_crm`; бонус, если CRM заявлена в форме, но на сайте не видна; небольшой бонус за «все лиды вовремя». |

### Столб 3 (`recommendation`)

| Блок | Вес | Содержание |
|------|-----|------------|
| Форма | 40% | Q8 upsell + Q9 churn; при `no_crm` лёгкие штрафы к upsell/churn. |
| Сайт | 38% | Тарифы, портал, биллинг, персонализация, A/B, лояльность, отзывы, NPS и т.п. — **или** усечённый вывод из формы. |
| Нарратив Q10 | 22% | Снижение за выбранные фрустрации, релевантные росту/фокусу. |

### Столб 4 (`analytics`)

| Блок | Вес | Содержание |
|------|-----|------------|
| Форма | 34% | Старт с «уверенности в измерениях»; сильные минусы за `cant_measure_whats_working`, комбинации с `too_many_tools`, за `revenue_doesnt_scale`. |
| Сайт: трекинг | 38% | GA4/GTM, product analytics, пиксели, behavior — **или** смесь с формой при пустом скане. |
| Продвинутый слой | 28% | Attribution, BI, A/B, связка CRM+аналитика, кейсы — **или** вывод из формы при пустом скане. |

### Итоговая интерпретация (`score_interpretation`)

Текстовая банд-оценка по **среднему** четырёх столбов (пороги ориентировочно **80 / 62 / 42 / 22**): от «сильная операционка» до «ранний / реактивный движок»).

### Дополнительные поля в `calculate_all_scores`

- `signals_count` — число сигналов enrichment (или сумма длин списков в `detected_tools`).
- `website_analysis_limited` — `true`, если `signals_count == 0`.
- `detected_tools_lines` — строки для отладки/логов.

Точные коэффициенты и баллы за отдельные теги см. в **`app/services/scoring.py`**.

---

## Лицензия и контакты

Проект **AVOX Systems** — https://avox.systems
