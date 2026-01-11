
import asyncio
import random
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Настройка логов
logging.basicConfig(level=logging.INFO)

# --- НАСТРОЙКИ ---
API_TOKEN = '8381301732:AAEesMo1ziDhIxr5vOwgyoMefDdH38nZ5jY'
ADMIN_ID = 8066060450
SHOP_LINK = 'https://t.me/freezebotnet'
INST_LINK = 'https://t.me/instru_frezee'

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# "Базы данных" (очищаются при перезагрузке)
users_db = {}  # {user_id: "Имя Фамилия"}
subscriptions = {}  # {user_id: datetime_end}
user_violations = {}  # {user_id: warnings_count, "freezes_id": count}


class AttackState(StatesGroup):
    waiting_for_username = State()


class AdminMenuState(StatesGroup):
    waiting_for_days = State()


# --- КЛАВИАТУРЫ ---

def get_main_menu():
    buttons = [
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
         InlineKeyboardButton(text="❄️ Запустить", callback_data="start_attack")],
        [InlineKeyboardButton(text="💰 Магазин", callback_data="shop"),
         InlineKeyboardButton(text="📜 Инструкция", url=INST_LINK)],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_shop_keyboard():
    buttons = [
        [InlineKeyboardButton(text="Купить подписку", url=SHOP_LINK)],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# --- ОБРАБОТЧИКИ ---

@router.message(Command("start"))
async def send_welcome(message: types.Message):
    # Запоминаем имя пользователя для админ-меню
    users_db[message.from_user.id] = message.from_user.full_name
    await message.answer("Привет! Добро пожаловать в главное меню.", reply_markup=get_main_menu())


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(call: types.CallbackQuery):
    await call.message.edit_text("Привет! Добро пожаловать в главное меню.", reply_markup=get_main_menu())
    await call.answer()


# ПРОФИЛЬ
@router.callback_query(F.data == "profile")
async def show_profile(call: types.CallbackQuery):
    user_id = call.from_user.id
    username = call.from_user.first_name

    sub_active = user_id in subscriptions and subscriptions[user_id] > datetime.now()
    sub_status = f"активна (до {subscriptions[user_id].strftime('%d.%m.%Y')}) ✅" if sub_active else "отсутствует ❌"

    total_freezes = user_violations.get(f"freezes_{user_id}", 0)
    warnings = user_violations.get(user_id, 0)

    text = (
        f"<b>Привет, {username}!</b>\n\n"
        f"<b>Статус подписки:</b> {sub_status}\n"
        f"<b>Всего заморозок:</b> {total_freezes} 🎯\n"
        f"<b>Предупреждения:</b> {warnings} ⚠️"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


# СТАТИСТИКА
@router.callback_query(F.data == "stats")
async def show_stats(call: types.CallbackQuery):
    user_id = call.from_user.id
    if user_id in subscriptions and subscriptions[user_id] > datetime.now():
        remains = subscriptions[user_id] - datetime.now()
        days = remains.days
        hours, _ = divmod(remains.seconds, 3600)
        time_str = f"{days}д. {hours}ч."
    else:
        time_str = "отсутствует ❌"

    text = f"📊 <b>Ваша статистика:</b>\n\n🕒 Время подписки: <code>{time_str}</code>"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

# МАГАЗИН
@router.callback_query(F.data == "shop")
async def show_shop(call: types.CallbackQuery):
    text = (
        "<b>Активные подписки:</b>\n\n"
        "❄️ День - 3$\n"
        "❄️ Неделя - 5$\n"
        "❄️ Месяц - 10$\n"
        "❄️ Навсегда - 20$"
    )
    await call.message.edit_text(text, reply_markup=get_shop_keyboard(), parse_mode="HTML")
    await call.answer()


# --- АДМИН-МЕНЮ /frezemenu ---

@router.message(Command("frezemenu"))
async def freeze_menu(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    if not users_db:
        await message.answer("Список пользователей пуст 🤷‍♂️")
        return

    kb_buttons = []
    for user_id, name in users_db.items():
        kb_buttons.append([InlineKeyboardButton(text=f"👤 {name}", callback_data=f"manage_{user_id}")])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await message.answer("<b>Все пользователи бота:</b>", reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("manage_"))
async def manage_user(call: types.CallbackQuery, state: FSMContext):
    target_id = call.data.split("_")[1]
    target_name = users_db.get(int(target_id), "Неизвестный")
    await state.update_data(target_id=target_id)
    await call.message.answer(f"👤 Пользователь: <b>{target_name}</b>\n🎯 Введите дни подписки:", parse_mode="HTML")
    await state.set_state(AdminMenuState.waiting_for_days)
    await call.answer()


@router.message(AdminMenuState.waiting_for_days)
async def process_days_menu(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    data = await state.get_data()
    target_id = int(data['target_id'])

    try:
        days = int(message.text)

        # Ограничитель, чтобы бот не падал от слишком больших чисел
        if days > 36500:  # Больше 100 лет
            days = 36500

        end_date = datetime.now() + timedelta(days=days)
        subscriptions[target_id] = end_date

        await message.answer(
            f"✅ Успешно! Юзеру <code>{target_id}</code> выдана подписка на {days} дн. (до {end_date.strftime('%d.%m.%Y')})",
            parse_mode="HTML")

        try:
            await bot.send_message(target_id, f"🎉 Админ активировал вам подписку на {days} дней!")
        except:
            pass

        await state.clear()
    except ValueError:
        await message.answer("⚠️ Введите число дней цифрами (например, 30).")
    except OverflowError:
        await message.answer("⚠️ Число слишком большое! Попробуйте поменьше (например, 3650).")
# --- ЗАПУСК АТАКИ ---

@router.callback_query(F.data == "start_attack")
async def start_attack_cmd(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if user_id not in subscriptions or subscriptions[user_id] < datetime.now():
        await call.message.answer("❌ У вас нет активной подписки!", reply_markup=get_shop_keyboard())
        return
    await call.message.answer("Введите @username жертвы —")
    await state.set_state(AttackState.waiting_for_username)
    await call.answer()


@router.message(AttackState.waiting_for_username)
async def process_attack(message: types.Message, state: FSMContext):
    username = message.text.replace("@", "").strip()
    if len(username) < 5:
        await message.answer("⚠️ введите конкретный @username")
        return

    await state.clear()

    # Имитируем ДЦ (для системы варнов)
    sim_dc = random.choice([1, 2, 3, 4, 5])

    if sim_dc in [2, 4]:
        count = user_violations.get(message.from_user.id, 0) + 1
        user_violations[message.from_user.id] = count
        if count >= 3:
            await message.answer("⚠️ Нарушение 3/3\n🚫 Подписка обнулена.")
            subscriptions[message.from_user.id] = datetime.now()  # Сбрасываем подписку

user_violations[message.from_user.id] = 0
        else:
            await message.answer(f"⚠️ замечено нарушение {count}/3")
    else:
        # Успешный запуск с задержкой
        wait = random.randint(10, 120)
        await message.answer(f"⏳ Запрос для @{username} отправлен... (DC{sim_dc})\nОжидайте от 10 сек до 2 мин.")

        await asyncio.sleep(wait)

        # Считаем заморозку в профиль
        user_violations[f"freezes_{message.from_user.id}"] = user_violations.get(f"freezes_{message.from_user.id}",
                                                                                 0) + 1

        suc, fail = random.randint(1, 400), random.randint(1, 400)
        report = (
            f"======================================\n"
            f"🎯 Пользователь: @{username}\n"
            f"❄️ Успешно: {suc}\n"
            f"❄️ Неудачно: {fail}\n"
            f"======================================"
        )
        await message.answer(report)


# --- ГЛАВНЫЙ ЗАПУСК ---

async def main():
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if name == 'main':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
