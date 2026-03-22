from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Сделать заказ", callback_data="make_order")],
        [InlineKeyboardButton(text="🔄 Повторить последний заказ", callback_data="repeat_order")],
        [InlineKeyboardButton(text="📋 Мои заказы", callback_data="my_orders")],
        [InlineKeyboardButton(text="📞 Связаться с диспетчером", callback_data="contact_dispatcher")],
        [InlineKeyboardButton(text="✏️ Изменить мои данные", callback_data="edit_profile")],
    ])


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Новые заказы", callback_data="new_orders")],
        [InlineKeyboardButton(text="⚙️ Активные заказы", callback_data="active_orders")],
        [InlineKeyboardButton(text="📋 История заказов", callback_data="all_orders")],
        [InlineKeyboardButton(text="🍞 Управление меню", callback_data="manage_menu")],
    ])


def manage_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить продукт", callback_data="add_product")],
        [InlineKeyboardButton(text="❌ Удалить продукт", callback_data="delete_product")],
        [InlineKeyboardButton(text="📋 Список продуктов", callback_data="list_products")],
    ])


def order_confirmation() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_order")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_order")],
    ])


def order_action(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_{order_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order_id}"),
        ]
    ])


def date_keyboard() -> InlineKeyboardMarkup:
    """Кнопки с ближайшими 7 днями"""
    buttons = []
    today = datetime.now()

    days_ru = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    for i in range(7):
        day = today + timedelta(days=i)
        date_str = day.strftime("%d.%m.%Y")
        day_name = days_ru[day.weekday()]

        if i == 0:
            label = f"📅 Сегодня {date_str}"
        elif i == 1:
            label = f"📅 Завтра {date_str}"
        else:
            label = f"{day_name} {date_str}"

        buttons.append([
            InlineKeyboardButton(text=label, callback_data=f"date_{date_str}")
        ])

    buttons.append([InlineKeyboardButton(text="❌ Отменить заказ", callback_data="cancel_order")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def time_keyboard() -> InlineKeyboardMarkup:
    """Кнопки с временем с 06:00 до 20:00"""
    times = [
        "06:00", "07:00", "08:00",
        "09:00", "10:00", "11:00",
        "12:00", "13:00", "14:00",
        "15:00", "16:00", "17:00",
        "18:00", "19:00", "20:00",
        "21:00", "22:00", "23:00",
    ]

    buttons = []
    row = []
    for i, t in enumerate(times):
        row.append(InlineKeyboardButton(text=t, callback_data=f"time_{t}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="❌ Отменить заказ", callback_data="cancel_order")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def delivery_type_keyboard() -> InlineKeyboardMarkup:
    """Выбор способа получения"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚚 Доставка", callback_data="type_delivery")],
        [InlineKeyboardButton(text="🏪 Самовывоз", callback_data="type_pickup")],
        [InlineKeyboardButton(text="❌ Отменить заказ", callback_data="cancel_order")],
    ])


def order_status_keyboard(order_id: int, delivery_type: str, current_status: str = None) -> InlineKeyboardMarkup:
    """Показывает только СЛЕДУЮЩИЙ шаг"""

    if delivery_type == "delivery":
        flow = ["preparing", "on_way", "delivered"]
        labels = {
            "preparing": "👨‍🍳 Готовится",
            "on_way":    "🚚 В пути",
            "delivered": "✅ Доставлен",
        }
    else:
        flow = ["preparing", "ready", "given"]
        labels = {
            "preparing": "👨‍🍳 Готовится",
            "ready":     "📦 Готов к выдаче",
            "given":     "✅ Выдан",
        }

    # Находим следующий статус
    if current_status is None:
        next_status = flow[0]
    elif current_status in flow:
        idx = flow.index(current_status)
        if idx + 1 < len(flow):
            next_status = flow[idx + 1]
        else:
            return None
    else:
        next_status = flow[0]

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=labels[next_status],
            callback_data=f"status_{next_status}_{order_id}"
        )]
    ])


def edit_profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Изменить имя", callback_data="edit_contact")],
        [InlineKeyboardButton(text="🏢 Изменить организацию", callback_data="edit_organization")],
        [InlineKeyboardButton(text="📞 Изменить телефон", callback_data="edit_phone")],
        [InlineKeyboardButton(text="🏦 ИНН", callback_data="edit_inn")],
        [InlineKeyboardButton(text="💳 Расчётный счёт", callback_data="edit_bank_account")],
        [InlineKeyboardButton(text="🏦 МФО", callback_data="edit_mfo")],
        [InlineKeyboardButton(text="🏛 Банк", callback_data="edit_bank_name")],
        [InlineKeyboardButton(text="📍 Адрес", callback_data="edit_legal_address")],
    ])


def client_reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Сделать заказ"), KeyboardButton(text="🔄 Повторить заказ")],
            [KeyboardButton(text="📋 Мои заказы"), KeyboardButton(text="📞 Диспетчер")],
            [KeyboardButton(text="✏️ Мои данные")],
        ],
        resize_keyboard=True
    )


def admin_reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Новые заказы"), KeyboardButton(text="⚙️ Активные заказы")],
            [KeyboardButton(text="📋 История заказов"), KeyboardButton(text="🍞 Управление меню")],
            [KeyboardButton(text="🔍 Найти заказ"), KeyboardButton(text="📅 Заказы по дате")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📥 Экспорт в Excel")],
            [KeyboardButton(text="📢 Рассылка"), KeyboardButton(text="💰 Договорные цены")],
            [KeyboardButton(text="👥 Клиенты"), KeyboardButton(text="⏸ Пауза")],
            [KeyboardButton(text="▶️ Возобновить")],
        ],
        resize_keyboard=True
    )