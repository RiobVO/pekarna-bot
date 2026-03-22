# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Запуск и разработка

```bash
# Запуск бота
python main.py

# Линтер
.venv/Scripts/ruff check .
```

При первом запуске автоматически создаётся `bakery.db` (SQLite). Тесты не настроены.

## Архитектура

Telegram-бот для пекарни (интерфейс на русском/узбекском), построенный на **aiogram 3.x**.

**Точка входа:** `main.py` — создаёт `Bot`, `Dispatcher` с `MemoryStorage`, регистрирует роутеры (сначала `admin`, потом `client`), инициализирует БД, запускает APScheduler для утреннего отчёта в 08:00 (`Asia/Tashkent`) первому админу (`ADMIN_ID`), затем запускает polling.

**Порядок регистрации роутеров важен:** `admin.router` подключается раньше `client.router`, поэтому admin-хендлеры имеют приоритет.

### Хендлеры

- **`handlers/admin.py`** — весь функционал диспетчера, защищён проверкой `is_admin()`:
  - Управление заказами: просмотр новых/активных/всех, принять, отклонить (FSM для причины), смена статуса
  - Цепочки статусов: доставка `new → accepted → preparing → on_way → delivered`, самовывоз `new → accepted → preparing → ready → given`
  - CRUD продуктов (добавить/удалить) через `AdminState` FSM
  - Список клиентов, договорные цены (`ClientPrice`), рассылка, экспорт в Excel через `openpyxl`
  - Поиск заказа, фильтр по дате, статистика
  - Пауза/возобновление приёма заказов (переключает `config.bot_paused`)

- **`handlers/client.py`** — клиентские сценарии:
  - `/start` проверяет регистрацию; новые пользователи проходят `OrderState` FSM: `entering_contact → entering_organization → entering_phone`
  - FSM заказа (`OrderState`): `choosing_products → entering_quantity → entering_comment → confirming`, плюс inline-коллбэки для типа доставки, даты, времени
  - Редактирование профиля: имя, организация, телефон, ИНН, расчётный счёт, МФО, банк, адрес
  - История заказов, оценка (1–5 звёзд отправляется после финального статуса)
  - Повтор последнего заказа (`repeat_order`)
  - Защита от спама: >15 сообщений в минуту блокируются через `_spam_tracker`

### Конфигурация (`config.py`)

Переменные `.env`:
- `BOT_TOKEN` — токен Telegram-бота
- `ADMIN_ID` — список ID админов через запятую (например `123456,789012`); первый (`ADMIN_ID`) получает утренний отчёт
- `MIN_ORDER_SUM` — минимальная сумма заказа в сумах (по умолчанию `50000`)
- `DATABASE_URL` — строка подключения PostgreSQL (Railway); если не задана, используется SQLite

`is_admin(user_id)` проверяет по всему списку `ADMIN_IDS`. `bot_paused: bool` — флаг уровня модуля, изменяется в рантайме.

### База данных (`database/`)

- `db.py`: асинхронный движок SQLAlchemy на `aiosqlite`; при наличии `DATABASE_URL` (Railway) использует PostgreSQL через `asyncpg` (автозамена `postgres://` → `postgresql+asyncpg://`)
- `models.py`: модели `Client`, `Product`, `Order`, `OrderItem`, `ClientPrice`
  - `Client` содержит реквизиты: `inn`, `bank_account`, `mfo`, `bank_name`, `legal_address` (все nullable)
  - `OrderItem.product_name` хранится как **строка** (не FK) — история сохраняется при переименовании/удалении продукта
  - `Order.delivery_date` хранится как строка `DD.MM.YYYY`
  - `Order.status_message_id` хранит ID последнего статусного сообщения клиенту (для редактирования)
  - `ClientPrice` переопределяет `Product.price` для конкретного клиента; хендлеры проверяют её перед показом списка

### Ключевые паттерны

- Все операции с БД: `async with session_maker() as session` — одна сессия на вызов хендлера
- Все клавиатуры (inline и reply) — в `keyboards.py`; `date_keyboard()` динамически генерирует ближайшие 7 дней, `order_status_keyboard()` возвращает `None` когда статус финальный
- Проверка прав администратора выполняется внутри каждого хендлера через `is_admin()`, а не на уровне роутера
