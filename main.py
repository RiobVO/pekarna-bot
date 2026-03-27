import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import ErrorEvent
from aiogram.exceptions import TelegramBadRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, func
from datetime import datetime

from config import BOT_TOKEN, ADMIN_ID
from database.db import create_db, session_maker
from database.models import Order, Client, OrderItem, Product
from handlers import client, admin

logging.basicConfig(level=logging.WARNING)


async def send_morning_report(bot: Bot):
    today = datetime.now().strftime("%d.%m.%Y")

    async with session_maker() as session:
        # Заказы на сегодня
        today_orders_result = await session.execute(
            select(Order).where(Order.delivery_date == today)
        )
        today_orders = today_orders_result.scalars().all()

        # Активные прямо сейчас
        active = await session.execute(
            select(func.count(Order.id)).where(
                Order.status.in_(["accepted", "preparing", "on_way", "ready"])
            )
        )
        active_count = active.scalar()

        # Всего клиентов
        clients_count_result = await session.execute(select(func.count(Client.id)))
        clients_count = clients_count_result.scalar()

        # Подсчёт выручки и формирование текста заказов
        total_revenue = 0
        if not today_orders:
            orders_text = "📭 Заказов на сегодня нет."
        else:
            orders_text = f"📦 Заказов на сегодня: {len(today_orders)}\n"
            for order in today_orders:
                client_obj = await session.get(Client, order.client_id)
                type_icon = "🚚" if order.delivery_type == "delivery" else "🏪"
                client_name = client_obj.contact_name if client_obj else "?"
                orders_text += f"  {type_icon} #{order.id} — {client_name} в {order.delivery_time}\n"

                items_result = await session.execute(
                    select(OrderItem).where(OrderItem.order_id == order.id)
                )
                for item in items_result.scalars().all():
                    product_result = await session.execute(
                        select(Product).where(Product.name == item.product_name)
                    )
                    product = product_result.scalars().first()
                    if product:
                        total_revenue += product.price * item.quantity

    revenue_line = f"💰 Ожидаемая выручка: {total_revenue:,} сум\n" if total_revenue > 0 else ""

    text = (
        f"🌅 ДОБРОЕ УТРО! Отчёт на {today}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{orders_text}"
        f"━━━━━━━━━━━━━━━\n"
        f"{revenue_line}"
        f"⚙️ Активных заказов: {active_count}\n"
        f"👥 Всего клиентов: {clients_count}"
    )

    try:
        await bot.send_message(ADMIN_ID, text)
    except Exception as e:
        logging.error(f"send_morning_report failed: {e}")


async def main():
    bot = Bot(token=BOT_TOKEN)
    redis_url = os.getenv("REDIS_URL")
    storage = RedisStorage.from_url(redis_url) if redis_url else MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.include_router(admin.router)
    dp.include_router(client.router)

    @dp.errors()
    async def error_handler(event: ErrorEvent):
        err = str(event.exception)
        if isinstance(event.exception, TelegramBadRequest) and (
            "query is too old" in err or "message is not modified" in err
        ):
            return True  # подавляем безобидные ошибки Telegram
        logging.error(f"Unhandled error: {event.exception}")

    await create_db()

    # Планировщик — отчёт каждый день в 08:00
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    scheduler.add_job(
        send_morning_report,
        trigger="cron",
        hour=8,
        minute=0,
        args=[bot]
    )
    scheduler.start()

    print("✅ Бот запущен!")

    try:
        await dp.start_polling(bot)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        print("🔴 Бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
