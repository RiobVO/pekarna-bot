import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from database.db import session_maker
from database.models import Client, Product, Order, OrderItem, ClientPrice
from keyboards import (
    order_confirmation, date_keyboard, time_keyboard,
    delivery_type_keyboard, admin_reply_menu, client_reply_menu, edit_profile_keyboard
)
from config import ADMIN_ID, is_admin, MIN_ORDER_SUM
from datetime import datetime
from collections import defaultdict


# Антиспам: {user_id: [timestamps]}
_spam_tracker: dict = defaultdict(list)

def is_spam(user_id: int) -> bool:
    now = datetime.now().timestamp()
    times = [t for t in _spam_tracker[user_id] if now - t < 60]
    times.append(now)
    _spam_tracker[user_id] = times
    # Удаляем пользователей без активности за последние 5 минут
    stale = [uid for uid, ts in _spam_tracker.items() if not ts or now - ts[-1] > 300]
    for uid in stale:
        del _spam_tracker[uid]
    return len(times) > 15


router = Router()


class OrderState(StatesGroup):
    # Регистрация
    entering_contact = State()
    entering_organization = State()
    entering_phone = State()
    entering_inn = State()
    entering_bank_account = State()
    entering_mfo = State()
    entering_bank_name = State()
    entering_legal_address = State()
    # Заказ
    choosing_products = State()
    entering_quantity = State()
    entering_address = State()
    entering_comment = State()
    confirming = State()


class EditProfileState(StatesGroup):
    choosing_field = State()
    entering_value = State()


# ─── РЕГИСТРАЦИЯ ───────────────────────────────────────

@router.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    if is_spam(message.from_user.id):
        await message.answer("⛔ Слишком много запросов. Подождите минуту.")
        return
    if is_admin(message.from_user.id):
        await message.answer("👋 Привет, диспетчер!", reply_markup=admin_reply_menu())
        return

    async with session_maker() as session:
        client = await session.execute(
            select(Client).where(Client.telegram_id == message.from_user.id)
        )
        client = client.scalar_one_or_none()

    if client:
        await message.answer(
            f"👋 Привет, <b>{client.contact_name}</b>!\n🏢 {client.organization}",
            reply_markup=client_reply_menu(),
            parse_mode="HTML"
        )
    else:
        await state.set_state(OrderState.entering_contact)
        await message.answer(
            "👋 <b>Добро пожаловать!</b>\n\n"
            "Для начала давайте познакомимся.\n"
            "Введите ваше имя и фамилию:",
            parse_mode="HTML"
        )


@router.message(OrderState.entering_contact)
async def enter_contact(message: Message, state: FSMContext):
    await state.update_data(contact_name=message.text)
    await state.set_state(OrderState.entering_organization)
    await message.answer("🏢 Введите название вашей организации:")


@router.message(OrderState.entering_organization)
async def enter_organization(message: Message, state: FSMContext):
    await state.update_data(organization=message.text)
    await state.set_state(OrderState.entering_phone)
    await message.answer("📞 Введите номер телефона:")


@router.message(OrderState.entering_phone)
async def enter_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not re.match(r"^\+?[0-9]{9,13}$", phone):
        await message.answer(
            "❌ Неверный формат номера!\n"
            "Пример: +998901234567\n\n"
            "Попробуйте ещё раз:"
        )
        return

    await state.update_data(phone=phone)
    await state.set_state(OrderState.entering_inn)
    await message.answer("🏦 Введите ИНН организации (9 цифр):")


@router.message(OrderState.entering_inn)
async def enter_inn(message: Message, state: FSMContext):
    inn = message.text.strip()
    if not re.match(r"^\d{9}$", inn):
        await message.answer("❌ ИНН должен содержать ровно 9 цифр.")
        return
    await state.update_data(inn=inn)
    await state.set_state(OrderState.entering_bank_account)
    await message.answer("💳 Введите расчётный счёт (20 цифр):")


@router.message(OrderState.entering_bank_account)
async def enter_bank_account(message: Message, state: FSMContext):
    account = message.text.strip()
    if not re.match(r"^\d{20}$", account):
        await message.answer("❌ Расчётный счёт должен содержать ровно 20 цифр.")
        return
    await state.update_data(bank_account=account)
    await state.set_state(OrderState.entering_mfo)
    await message.answer("🏦 Введите МФО банка (5 цифр):")


@router.message(OrderState.entering_mfo)
async def enter_mfo(message: Message, state: FSMContext):
    mfo = message.text.strip()
    if not re.match(r"^\d{5}$", mfo):
        await message.answer("❌ МФО должен содержать ровно 5 цифр.")
        return
    await state.update_data(mfo=mfo)
    await state.set_state(OrderState.entering_bank_name)
    await message.answer("🏛 Введите название банка:")


@router.message(OrderState.entering_bank_name)
async def enter_bank_name(message: Message, state: FSMContext):
    await state.update_data(bank_name=message.text.strip())
    await state.set_state(OrderState.entering_legal_address)
    await message.answer("📍 Введите юридический/фактический адрес:")


@router.message(OrderState.entering_legal_address)
async def enter_legal_address(message: Message, state: FSMContext):
    legal_address = message.text.strip()
    data = await state.get_data()

    async with session_maker() as session:
        client = Client(
            telegram_id=message.from_user.id,
            contact_name=data["contact_name"],
            organization=data["organization"],
            phone=data["phone"],
            inn=data["inn"],
            bank_account=data["bank_account"],
            mfo=data["mfo"],
            bank_name=data["bank_name"],
            legal_address=legal_address,
        )
        session.add(client)
        await session.commit()

    await state.clear()
    await message.answer(
        f"✅ <b>Регистрация завершена!</b>\n\n"
        f"👤 {data['contact_name']}\n"
        f"🏢 {data['organization']}\n"
        f"📞 {data['phone']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🏦 ИНН: {data['inn']}\n"
        f"💳 Р/С: {data['bank_account']}\n"
        f"🏦 МФО: {data['mfo']}\n"
        f"🏛 {data['bank_name']}\n"
        f"📍 {legal_address}\n\n"
        f"Используйте кнопки меню ниже.",
        reply_markup=client_reply_menu(),
        parse_mode="HTML"
    )


# ─── REPLY КНОПКИ КЛИЕНТА ──────────────────────────────
# Зарегистрированы ДО FSM-хендлеров — перехватывают нажатия даже во время заказа

@router.message(F.text == "🛒 Сделать заказ")
async def btn_make_order(message: Message, state: FSMContext):
    await state.clear()
    await _start_ordering(message, state, message.from_user.id)


@router.message(F.text == "🔄 Повторить заказ")
async def btn_repeat_order(message: Message, state: FSMContext):
    await state.clear()
    await _do_repeat_order(message, state, message.from_user.id)


@router.message(F.text == "📋 Мои заказы")
async def btn_my_orders(message: Message, state: FSMContext):
    await state.clear()
    await _show_my_orders(message.from_user.id, message)


@router.message(F.text == "📞 Диспетчер")
async def btn_contact(message: Message, state: FSMContext):
    await state.clear()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать диспетчеру", url=f"tg://user?id={ADMIN_ID}")]
    ])
    await message.answer(
        "📞 Нажмите кнопку ниже чтобы написать диспетчеру напрямую:",
        reply_markup=keyboard
    )


@router.message(F.text == "✏️ Мои данные")
async def btn_edit_profile(message: Message, state: FSMContext):
    await state.clear()
    await _show_edit_profile(message)


# ─── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ───────────────────────────

async def _start_ordering(message: Message, state: FSMContext, user_id: int):
    import config
    if config.bot_paused:
        await message.answer(
            "⏸ Приём заказов временно приостановлен.\n"
            "Попробуйте позже или свяжитесь с диспетчером."
        )
        return

    async with session_maker() as session:
        products = await session.execute(select(Product))
        products = products.scalars().all()

        if not products:
            await message.answer("😔 Меню пока пустое. Попробуйте позже.")
            return

        client_obj = await session.execute(
            select(Client).where(Client.telegram_id == user_id)
        )
        client_obj = client_obj.scalar_one_or_none()

        if not client_obj:
            await message.answer("❌ Сначала зарегистрируйтесь — напишите /start")
            return

        custom_prices = await session.execute(
            select(ClientPrice).where(ClientPrice.client_id == client_obj.id)
        )
        custom_prices = {cp.product_id: cp.price for cp in custom_prices.scalars().all()}

    products_data = []
    text = "🛍 <b>МЕНЮ</b>\n\n"
    for i, p in enumerate(products, 1):
        actual_price = custom_prices.get(p.id, p.price)
        text += f"{i}. {p.name} — <b>{actual_price:,} сум</b>\n"
        products_data.append((p.id, p.name, actual_price))
    text += "\nВведите номер товара:"

    msg = await message.answer(text, parse_mode="HTML")
    await state.update_data(products=products_data, cart=[], order_msg_id=msg.message_id)
    await state.set_state(OrderState.choosing_products)


async def _show_my_orders(user_id: int, message: Message):
    async with session_maker() as session:
        client = await session.execute(
            select(Client).where(Client.telegram_id == user_id)
        )
        client = client.scalar_one_or_none()

        if not client:
            await message.answer("❌ Сначала зарегистрируйтесь — напишите /start")
            return

        orders = await session.execute(
            select(Order).where(Order.client_id == client.id).order_by(Order.id.desc()).limit(10)
        )
        orders = orders.scalars().all()

    if not orders:
        await message.answer("📋 У вас пока нет заказов.")
        return

    status_map = {
        "new": "🟡 Новый",
        "accepted": "✅ Принят",
        "rejected": "❌ Отклонён",
        "cancelled": "🚫 Отменён",
        "preparing": "👨‍🍳 Готовится",
        "on_way": "🚚 В пути",
        "ready": "📦 Готов к выдаче",
        "delivered": "✅ Доставлен",
        "given": "✅ Выдан",
    }

    for order in orders:
        created = order.created_at.strftime("%d.%m.%Y %H:%M") if order.created_at else ""
        text = (
            f"<b>Заказ #{order.id}</b>\n"
            f"📅 {order.delivery_date} в {order.delivery_time}\n"
            f"🕐 Оформлен: {created}\n"
            f"Статус: {status_map.get(order.status, order.status)}"
        )
        buttons = []
        if order.status == "new":
            buttons.append([
                InlineKeyboardButton(text="🚫 Отменить заказ", callback_data=f"cancel_my_{order.id}")
            ])
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
        )


async def _get_profile_display(user_id: int):
    async with session_maker() as session:
        result = await session.execute(
            select(Client).where(Client.telegram_id == user_id)
        )
        client = result.scalar_one_or_none()

    if not client:
        return "❌ Профиль не найден.", None

    text = (
        f"👤 <b>{client.contact_name}</b>\n"
        f"🏢 {client.organization}\n"
        f"📞 {client.phone}\n"
    )
    if any([client.inn, client.bank_account, client.mfo, client.bank_name, client.legal_address]):
        text += "━━━━━━━━━━━━━━━\n"
        if client.inn:
            text += f"🏦 ИНН: {client.inn}\n"
        if client.bank_account:
            text += f"💳 Р/С: {client.bank_account}\n"
        if client.mfo:
            text += f"🏦 МФО: {client.mfo}\n"
        if client.bank_name:
            text += f"🏛 {client.bank_name}\n"
        if client.legal_address:
            text += f"📍 {client.legal_address}\n"
    text += "\n✏️ Что хотите изменить?"
    return text, edit_profile_keyboard()


async def _show_edit_profile(message: Message):
    text, keyboard = await _get_profile_display(message.from_user.id)
    if keyboard is None:
        await message.answer(text)
    else:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


async def _do_repeat_order(message: Message, state: FSMContext, user_id: int):
    import config
    if config.bot_paused:
        await message.answer(
            "⏸ Приём заказов временно приостановлен.\n"
            "Попробуйте позже или свяжитесь с диспетчером."
        )
        return

    async with session_maker() as session:
        client = await session.execute(
            select(Client).where(Client.telegram_id == user_id)
        )
        client = client.scalar_one_or_none()

        if not client:
            await message.answer("❌ Сначала зарегистрируйтесь — напишите /start")
            return

        last_order = await session.execute(
            select(Order).where(Order.client_id == client.id).order_by(Order.id.desc())
        )
        last_order = last_order.scalars().first()

        if not last_order:
            await message.answer("📋 У вас пока нет заказов для повтора.")
            return

        items = await session.execute(
            select(OrderItem).where(OrderItem.order_id == last_order.id)
        )
        items = items.scalars().all()

    async with session_maker() as session:
        client_prices = await session.execute(
            select(ClientPrice).where(ClientPrice.client_id == client.id)
        )
        client_prices_map = {cp.product_id: cp.price for cp in client_prices.scalars().all()}

        cart = []
        for i in items:
            product = await session.execute(
                select(Product).where(Product.name == i.product_name)
            )
            product = product.scalars().first()
            actual_price = client_prices_map.get(product.id, product.price) if product else 0
            cart.append({
                "product_name": i.product_name,
                "quantity": i.quantity,
                "price": actual_price
            })

    total = sum(item["price"] * item["quantity"] for item in cart)
    text = "🔄 <b>ПОВТОР ЗАКАЗА</b>\n\n"
    for item in cart:
        subtotal = item["price"] * item["quantity"]
        text += f"• {item['product_name']} × {item['quantity']} шт = {subtotal:,} сум\n"
    text += f"\n<b>💰 Итого: {total:,} сум</b>"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оформить", callback_data="checkout")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_order")],
    ])
    msg = await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await state.update_data(cart=cart, order_msg_id=msg.message_id)
    await state.set_state(OrderState.choosing_products)


# ─── ЗАКАЗ ─────────────────────────────────────────────

@router.callback_query(F.data == "make_order")
async def make_order(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await _start_ordering(callback.message, state, callback.from_user.id)


@router.message(OrderState.choosing_products)
async def choose_product(message: Message, state: FSMContext):
    data = await state.get_data()
    products = data.get("products")
    if not products:
        await state.clear()
        return
    order_msg_id = data.get("order_msg_id")

    try:
        index = int(message.text) - 1
        if index < 0 or index >= len(products):
            raise ValueError
    except ValueError:
        try:
            await message.delete()
        except Exception:
            pass
        return

    try:
        await message.delete()
    except Exception:
        pass

    selected = products[index]
    await state.update_data(selected_product=selected)
    await state.set_state(OrderState.entering_quantity)

    text = (
        f"🛍 <b>МЕНЮ</b>\n\n"
        f"<b>{selected[1]}</b> — {selected[2]:,} сум\n\n"
        f"Сколько штук?"
    )
    if order_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=order_msg_id,
                text=text,
                parse_mode="HTML"
            )
            return
        except Exception:
            pass
    msg = await message.answer(text, parse_mode="HTML")
    await state.update_data(order_msg_id=msg.message_id)


@router.message(OrderState.entering_quantity)
async def enter_quantity(message: Message, state: FSMContext):
    try:
        quantity = int(message.text)
        if quantity <= 0:
            raise ValueError
    except ValueError:
        try:
            await message.delete()
        except Exception:
            pass
        return

    try:
        await message.delete()
    except Exception:
        pass

    data = await state.get_data()
    cart = data["cart"]
    selected = data["selected_product"]
    order_msg_id = data.get("order_msg_id")

    existing = next((item for item in cart if item["product_name"] == selected[1]), None)
    if existing:
        existing["quantity"] += quantity
    else:
        cart.append({"product_name": selected[1], "quantity": quantity, "price": selected[2]})
    await state.update_data(cart=cart)

    total = sum(item["price"] * item["quantity"] for item in cart)
    text = "🛒 <b>КОРЗИНА</b>\n\n"
    for item in cart:
        subtotal = item["price"] * item["quantity"]
        text += f"• {item['product_name']} × {item['quantity']} шт — {subtotal:,} сум\n"
    text += f"\n<b>💰 Итого: {total:,} сум</b>"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ещё", callback_data="add_more")],
        [InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_order")],
    ])
    await state.set_state(OrderState.choosing_products)

    if order_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=order_msg_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            return
        except Exception:
            pass
    msg = await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await state.update_data(order_msg_id=msg.message_id)


@router.callback_query(F.data == "add_more")
async def add_more(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    products = data["products"]

    text = "🛍 <b>МЕНЮ</b>\n\n"
    for i, p in enumerate(products, 1):
        text += f"{i}. {p[1]} — <b>{p[2]:,} сум</b>\n"
    text += "\nВведите номер товара:"

    await state.set_state(OrderState.choosing_products)
    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data == "checkout")
async def checkout(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    cart = data.get("cart", [])
    total = sum(item["price"] * item["quantity"] for item in cart)

    if total < MIN_ORDER_SUM:
        text = "🛒 <b>КОРЗИНА</b>\n\n"
        for item in cart:
            subtotal = item["price"] * item["quantity"]
            text += f"• {item['product_name']} × {item['quantity']} шт — {subtotal:,} сум\n"
        text += f"\n<b>💰 Итого: {total:,} сум</b>"
        text += f"\n\n⚠️ Минимальная сумма заказа: <b>{MIN_ORDER_SUM:,} сум</b>\nДобавьте ещё товаров."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить ещё", callback_data="add_more")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_order")],
        ])
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            pass
        return

    try:
        await callback.message.edit_text(
            "📦 <b>ОФОРМЛЕНИЕ ЗАКАЗА</b>\n\nВыберите способ получения:",
            reply_markup=delivery_type_keyboard(),
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("type_"))
async def choose_delivery_type(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    delivery_type = callback.data.split("type_")[1]
    await state.update_data(delivery_type=delivery_type)

    if delivery_type == "delivery":
        async with session_maker() as session:
            result = await session.execute(
                select(Client).where(Client.telegram_id == callback.from_user.id)
            )
            client = result.scalar_one_or_none()

        if client and client.legal_address:
            await state.update_data(delivery_address=client.legal_address)
            addr_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Верно", callback_data="addr_confirm")],
                [InlineKeyboardButton(text="✏️ Изменить адрес", callback_data="addr_change")],
                [InlineKeyboardButton(text="❌ Отменить заказ", callback_data="cancel_order")],
            ])
            try:
                await callback.message.edit_text(
                    f"📦 <b>ОФОРМЛЕНИЕ ЗАКАЗА</b>\n\n📍 Адрес доставки:\n<b>{client.legal_address}</b>\n\nВерно?",
                    reply_markup=addr_keyboard,
                    parse_mode="HTML"
                )
            except Exception:
                pass
        else:
            await state.set_state(OrderState.entering_address)
            try:
                await callback.message.edit_text(
                    "📦 <b>ОФОРМЛЕНИЕ ЗАКАЗА</b>\n\n📍 Введите адрес доставки:",
                    parse_mode="HTML"
                )
            except Exception:
                pass
    else:
        try:
            await callback.message.edit_text(
                "📦 <b>ОФОРМЛЕНИЕ ЗАКАЗА</b>\n\n📅 Выберите дату:",
                reply_markup=date_keyboard(),
                parse_mode="HTML"
            )
        except Exception:
            pass


@router.callback_query(F.data == "addr_confirm")
async def addr_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        await callback.message.edit_text(
            "📦 <b>ОФОРМЛЕНИЕ ЗАКАЗА</b>\n\n📅 Выберите дату доставки:",
            reply_markup=date_keyboard(),
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data == "addr_change")
async def addr_change(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(OrderState.entering_address)
    try:
        await callback.message.edit_text(
            "📦 <b>ОФОРМЛЕНИЕ ЗАКАЗА</b>\n\n📍 Введите новый адрес доставки:",
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.message(OrderState.entering_address)
async def enter_address(message: Message, state: FSMContext):
    address = message.text.strip()
    await state.update_data(delivery_address=address)

    try:
        await message.delete()
    except Exception:
        pass

    data = await state.get_data()
    order_msg_id = data.get("order_msg_id")

    if order_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=order_msg_id,
                text="📦 <b>ОФОРМЛЕНИЕ ЗАКАЗА</b>\n\n📅 Выберите дату доставки:",
                reply_markup=date_keyboard(),
                parse_mode="HTML"
            )
            return
        except Exception:
            pass
    await message.answer(
        "📦 <b>ОФОРМЛЕНИЕ ЗАКАЗА</b>\n\n📅 Выберите дату доставки:",
        reply_markup=date_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("date_"))
async def choose_date(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    date = callback.data.split("date_")[1]
    await state.update_data(delivery_date=date)
    try:
        await callback.message.edit_text(
            "📦 <b>ОФОРМЛЕНИЕ ЗАКАЗА</b>\n\n🕐 Выберите время:",
            reply_markup=time_keyboard(),
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("time_"))
async def choose_time(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    time_val = callback.data.split("time_")[1]
    data = await state.get_data()
    await state.update_data(delivery_time=time_val)

    cart = data["cart"]
    delivery_type = data.get("delivery_type", "delivery")
    type_icon = "🚚 Доставка" if delivery_type == "delivery" else "🏪 Самовывоз"

    text = "📦 <b>ОФОРМЛЕНИЕ ЗАКАЗА</b>\n\n"
    for item in cart:
        text += f"• {item['product_name']} × {item['quantity']} шт\n"
    text += f"\n📅 {data['delivery_date']} · {time_val}\n{type_icon}"
    text += "\n\n💬 Добавьте комментарий или напишите «-»:"

    await state.set_state(OrderState.entering_comment)
    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        pass


@router.message(OrderState.entering_comment)
async def enter_comment(message: Message, state: FSMContext):
    comment = message.text.strip()
    if comment == "-":
        comment = None
    await state.update_data(comment=comment)

    try:
        await message.delete()
    except Exception:
        pass

    data = await state.get_data()
    cart = data["cart"]
    order_msg_id = data.get("order_msg_id")

    total = sum(item["price"] * item["quantity"] for item in cart)
    delivery_type = data.get("delivery_type", "delivery")
    type_icon = "🚚 Доставка" if delivery_type == "delivery" else "🏪 Самовывоз"

    text = "📋 <b>ПОДТВЕРЖДЕНИЕ ЗАКАЗА</b>\n\n"
    for item in cart:
        subtotal = item["price"] * item["quantity"]
        text += f"• {item['product_name']} × {item['quantity']} шт = {subtotal:,} сум\n"
    text += f"\n<b>💰 Итого: {total:,} сум</b>"
    text += f"\n\n📅 {data['delivery_date']} · {data['delivery_time']}\n{type_icon}"
    if comment:
        text += f"\n💬 {comment}"

    await state.set_state(OrderState.confirming)

    if order_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=order_msg_id,
                text=text,
                parse_mode="HTML",
                reply_markup=order_confirmation()
            )
            return
        except Exception:
            pass
    msg = await message.answer(text, parse_mode="HTML", reply_markup=order_confirmation())
    await state.update_data(order_msg_id=msg.message_id)


@router.callback_query(F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext, bot):
    await callback.answer()
    data = await state.get_data()

    if not data.get("delivery_date") or not data.get("delivery_time") or not data.get("cart"):
        await callback.message.answer("❌ Что-то пошло не так. Начните заказ заново.")
        await state.clear()
        return

    delivery_type = data.get("delivery_type", "delivery")

    async with session_maker() as session:
        client = await session.execute(
            select(Client).where(Client.telegram_id == callback.from_user.id)
        )
        client = client.scalar_one_or_none()
        if not client:
            await callback.message.answer("❌ Профиль не найден. Напишите /start")
            await state.clear()
            return

        order = Order(
            client_id=client.id,
            delivery_date=data["delivery_date"],
            delivery_time=data["delivery_time"],
            delivery_type=delivery_type,
            status="new",
            comment=data.get("comment"),
            delivery_address=data.get("delivery_address")
        )
        session.add(order)
        await session.flush()

        for item in data["cart"]:
            session.add(OrderItem(
                order_id=order.id,
                product_name=item["product_name"],
                quantity=item["quantity"]
            ))
        await session.commit()
        order_id = order.id

    from keyboards import order_action
    total = 0
    items_text = ""
    for item in data["cart"]:
        price = item.get("price", 0)
        subtotal = price * item["quantity"]
        total += subtotal
        items_text += f"• {item['product_name']} × {item['quantity']} шт = {subtotal:,} сум\n"

    type_label = "🚚 Доставка" if delivery_type == "delivery" else "🏪 Самовывоз"
    comment_line = f"💬 {data['comment']}\n" if data.get("comment") else ""
    address_line = f"📍 {data['delivery_address']}\n" if delivery_type == "delivery" and data.get("delivery_address") else ""

    admin_text = (
        f"<b>📦 ЗАКАЗ #{order_id} · {type_label}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {client.contact_name}\n"
        f"🏢 {client.organization} · 📞 {client.phone}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{items_text}"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>💰 Итого: {total:,} сум</b>\n"
        f"📅 {data['delivery_date']} · {data['delivery_time']}\n"
        f"{address_line}"
        f"{comment_line}"
    )

    await bot.send_message(ADMIN_ID, admin_text, reply_markup=order_action(order_id), parse_mode="HTML")

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        f"✅ <b>Заказ #{order_id} отправлен!</b>\n\n"
        f"Ожидайте подтверждения от диспетчера.",
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data == "cancel_order")
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("❌ Заказ отменён.")


# ─── МОИ ЗАКАЗЫ + ОТМЕНА ───────────────────────────────

@router.callback_query(F.data == "my_orders")
async def my_orders(callback: CallbackQuery):
    await callback.answer()
    await _show_my_orders(callback.from_user.id, callback.message)


@router.callback_query(F.data.startswith("cancel_my_"))
async def cancel_my_order(callback: CallbackQuery, bot):
    await callback.answer()
    order_id = int(callback.data.split("cancel_my_")[1])

    async with session_maker() as session:
        order = await session.get(Order, order_id)
        if not order or order.status != "new":
            await callback.message.answer("❌ Заказ уже нельзя отменить.")
            return
        order.status = "cancelled"
        await session.commit()

    await bot.send_message(ADMIN_ID, f"🚫 Заказ #{order_id} отменён клиентом.")
    await callback.message.edit_text(
        callback.message.text + "\n\n🚫 ОТМЕНЁН",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "repeat_order")
async def repeat_order(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await _do_repeat_order(callback.message, state, callback.from_user.id)


# ─── СВЯЗАТЬСЯ С ДИСПЕТЧЕРОМ ───────────────────────────

@router.callback_query(F.data == "contact_dispatcher")
async def contact_dispatcher(callback: CallbackQuery):
    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать диспетчеру", url=f"tg://user?id={ADMIN_ID}")]
    ])
    await callback.message.answer(
        "📞 Нажмите кнопку ниже чтобы написать диспетчеру напрямую:",
        reply_markup=keyboard
    )


# ─── ИЗМЕНИТЬ ДАННЫЕ ───────────────────────────────────

@router.callback_query(F.data == "edit_profile")
async def edit_profile(callback: CallbackQuery):
    await callback.answer()
    text, keyboard = await _get_profile_display(callback.from_user.id)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("edit_"))
async def start_edit(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    field = callback.data.split("edit_")[1]
    field_names = {
        "contact": "имя и фамилию",
        "organization": "название организации",
        "phone": "номер телефона",
        "inn": "ИНН (9 цифр)",
        "bank_account": "расчётный счёт (20 цифр)",
        "mfo": "МФО банка (5 цифр)",
        "bank_name": "название банка",
        "legal_address": "юридический адрес",
    }
    await state.update_data(edit_field=field)
    await state.set_state(EditProfileState.entering_value)
    try:
        await callback.message.edit_text(f"✏️ Введите новое {field_names[field]}:")
    except Exception:
        await callback.message.answer(f"✏️ Введите новое {field_names[field]}:")


@router.message(EditProfileState.entering_value)
async def save_edit(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data["edit_field"]
    value = message.text.strip()

    if field == "phone":
        if not re.match(r"^\+?[0-9]{9,13}$", value):
            await message.answer(
                "❌ Неверный формат номера!\n"
                "Пример: +998901234567\n\n"
                "Попробуйте ещё раз:"
            )
            return
    elif field == "inn":
        if not re.match(r"^\d{9}$", value):
            await message.answer("❌ ИНН должен содержать ровно 9 цифр.")
            return
    elif field == "bank_account":
        if not re.match(r"^\d{20}$", value):
            await message.answer("❌ Расчётный счёт должен содержать ровно 20 цифр.")
            return
    elif field == "mfo":
        if not re.match(r"^\d{5}$", value):
            await message.answer("❌ МФО должен содержать ровно 5 цифр.")
            return

    field_map = {
        "contact": "contact_name",
        "organization": "organization",
        "phone": "phone",
        "inn": "inn",
        "bank_account": "bank_account",
        "mfo": "mfo",
        "bank_name": "bank_name",
        "legal_address": "legal_address",
    }

    async with session_maker() as session:
        client = await session.execute(
            select(Client).where(Client.telegram_id == message.from_user.id)
        )
        client = client.scalar_one_or_none()
        if not client:
            await state.clear()
            return
        setattr(client, field_map[field], value)
        await session.commit()

    await state.clear()
    await message.answer("✅ Данные обновлены!")


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass


# ─── ОЦЕНКА ────────────────────────────────────────────

@router.callback_query(F.data.startswith("rate_"))
async def rate_order(callback: CallbackQuery, bot):
    await callback.answer()
    parts = callback.data.split("_")
    stars = int(parts[1])
    order_id = int(parts[2])

    emoji_map = {0: "—", 1: "😞", 2: "😐", 3: "🙂", 4: "😊", 5: "🤩"}
    star_text = emoji_map.get(stars, "🙂")

    if stars == 0:
        await callback.message.edit_text("Спасибо! Будем рады видеть вас снова 🙌")
    else:
        await callback.message.edit_text(f"Спасибо за оценку! {star_text}")
        await bot.send_message(
            ADMIN_ID,
            f"📊 Заказ #{order_id} — оценка: {star_text} ({stars}/5)"
        )
