from dotenv import load_dotenv
import os
import sys

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    sys.exit("❌ BOT_TOKEN не задан в .env")

# Поддержка нескольких админов: ADMIN_ID=123456,789012
_admin_raw = os.getenv("ADMIN_ID", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_raw.split(",") if x.strip()]
if not ADMIN_IDS:
    sys.exit("❌ ADMIN_ID не задан в .env")
ADMIN_ID = ADMIN_IDS[0]  # основной админ для уведомлений


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


bot_paused = False  # глобальный флаг паузы

MIN_ORDER_SUM = int(os.getenv("MIN_ORDER_SUM", "50000"))  # минимальная сумма заказа в сумах
