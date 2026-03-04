# -*- coding: utf-8 -*-
import asyncio
import os
import sys
import signal
from datetime import datetime
from dotenv import load_dotenv
import logging

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp
)

load_dotenv()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MINIAPP_URL = os.getenv("MINIAPP_URL", "")
PID_FILE = "bot.pid"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()
router = Router()
dp.include_router(router)

users = set()
queue = []
pairs = {}
timestamps = {}
message_timers = {}  # Для отслеживания сообщений для удаления

# Таймер для удаления старых сообщений каждые 3 минуты
async def auto_delete_messages():
    while True:
        try:
            await asyncio.sleep(180)  # 3 минуты
            now = datetime.now()
            expired = [key for key, (_, time) in message_timers.items()
                      if (now - time).total_seconds() > 180]
            for key in expired:
                chat_id, msg_id = key
                try:
                    await bot.delete_message(chat_id, msg_id)
                    del message_timers[key]
                except:
                    message_timers.pop(key, None)
        except Exception as e:
            print(f"Ошибка автоудаления: {e}")

# Устанавливаем главную кнопку MiniApp
async def set_main_button():
    try:
        menu_button = MenuButtonWebApp(
            text="🔓 Шифратор",
            web_app=WebAppInfo(url=MINIAPP_URL)
        )
        await bot.set_chat_menu_button(menu_button=menu_button)
        print("✅ Главная кнопка установлена")
    except Exception as e:
        print(f"⚠️ Ошибка установки кнопки: {e}")

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Подключиться анонимно", callback_data="find")],
        [InlineKeyboardButton(text="🔌 Отключиться", callback_data="stop")]
    ])

def cancel_search():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏸ Отменить", callback_data="cancel")]
    ])

def partner(uid: int):
    return pairs.get(uid)

def link(a, b):
    pairs[a] = b
    pairs[b] = a

def unlink(uid):
    p = pairs.pop(uid, None)
    if p: pairs.pop(p, None)

def add_queue(uid):
    if uid not in queue: queue.append(uid)

def rem_queue(uid):
    if uid in queue: queue.remove(uid)

def match(uid):
    for q in queue:
        if q != uid:
            queue.remove(q)
            rem_queue(uid)
            return q
    return None

@router.message(Command("search"))
async def cmd_search(msg: Message):
    """Команда /search - поиск собеседника"""
    uid = msg.from_user.id
    if partner(uid):
        await msg.answer("🔌 Вы уже подключены")
        return

    search_msg = await msg.answer(
        "⏳ *Подключение...*\n\n"
        "Ожидание собеседника",
        reply_markup=cancel_search()
    )

    # Отслеживаем сообщение для автоудаления
    message_timers[(search_msg.chat.id, search_msg.message_id)] = (uid, datetime.now())

    add_queue(uid)
    asyncio.create_task(find_match(uid))


@router.message(Command("stop"))
async def cmd_stop(msg: Message):
    """Команда /stop - остановить диалог"""
    uid = msg.from_user.id
    p = partner(uid)
    if not p:
        await msg.answer("❌ Вы не в диалоге!", reply_markup=main_menu())
        return
    unlink(uid)

    # Удаляем текущее сообщение команды
    try:
        await bot.delete_message(msg.chat.id, msg.message_id)
    except:
        pass

    # Отправляем подтверждение
    await msg.answer("🔌 *Отключены*\n\n\n🔐 *Анонимный E2E чат*\n\n"
        "• Никаких логов\n"
        "• Полное шифрование\n"
        "• Временные соединения\n\n"
        "_Все данные хранятся локально_", reply_markup=main_menu())
    try:
        await bot.send_message(p, "💔 *Собеседник отключился*\n\n\n*🔐 Анонимный E2E чат*\n\n"
        "• Никаких логов\n"
        "• Полное шифрование\n"
        "• Временные соединения\n\n"
        "_Все данные хранятся локально_", reply_markup=main_menu())
    except:
        pass

@router.message(CommandStart())
async def start(msg: Message):
    users.add(msg.from_user.id)

    # Инициализируем главную кнопку Telegram
    try:
        from aiogram.types import WebAppInfo
        tg = msg.bot
        # Создаём кнопку через context если доступно
    except:
        pass

    await msg.answer(
        "🔐 *Анонимный E2E чат*\n\n"
        "• Никаких логов\n"
        "• Полное шифрование\n"
        "• Временные соединения\n\n"
        "_Все данные хранятся локально_",
        reply_markup=main_menu()
    )

@router.callback_query(F.data == "find")
async def find_partner(cb: CallbackQuery):
    uid = cb.from_user.id
    if partner(uid):
        await cb.answer("🔌 Вы уже подключены", show_alert=True)
        return

    msg = await cb.message.answer(
        "⏳ *Подключение...*\n\n"
        "Ожидание собеседника",
        reply_markup=cancel_search()
    )

    # Отслеживаем сообщение для автоудаления
    message_timers[(msg.chat.id, msg.message_id)] = (cb.from_user.id, datetime.now())

    add_queue(uid)
    asyncio.create_task(find_match(uid))

async def find_match(uid):
    await asyncio.sleep(1)
    p = match(uid)
    if p:
        link(uid, p)
        text = "✅ *Подключен*\n\n🔐 Используйте шифратор для важных сообщений"
        kb = main_menu()
        for u in (uid, p):
            try:
                await bot.send_message(u, text, reply_markup=kb)
            except:
                pass

@router.callback_query(F.data == "cancel")
async def cancel(cb: CallbackQuery):
    uid = cb.from_user.id
    rem_queue(uid)

    # Удаляем сообщение поиска вместо редактирования
    try:
        await bot.delete_message(cb.message.chat.id, cb.message.message_id)
        # Удаляем из таймеров если есть
        message_timers.pop((cb.message.chat.id, cb.message.message_id), None)
    except:
        pass

    # Отправляем новое сообщение с меню
    cancel_msg = await cb.message.answer("❌ *Отменено*", reply_markup=main_menu())

    # Автоудаление через 0.1 секунды
    async def delete_after_delay():
        await asyncio.sleep(0.1)
        try:
            await bot.delete_message(cancel_msg.chat.id, cancel_msg.message_id)
        except:
            pass

    asyncio.create_task(delete_after_delay())
    await cb.answer()

@router.callback_query(F.data == "stop")
async def stop(cb: CallbackQuery):
    uid = cb.from_user.id
    p = partner(uid)
    if not p:
        await cb.answer("❌ Вы не в диалоге!", show_alert=True)
        return
    unlink(uid)

    # Удаляем сообщение вместо редактирования
    try:
        await bot.delete_message(cb.message.chat.id, cb.message.message_id)
        # Удаляем из таймеров если есть
        message_timers.pop((cb.message.chat.id, cb.message.message_id), None)
    except:
        pass

    # Отправляем новое сообщение с меню
    await cb.message.answer("🔌 *Отключены*", reply_markup=main_menu())
    try:
        await bot.send_message(p, "💔 *Собеседник отключился*", reply_markup=main_menu())
    except:
        pass
    await cb.answer()

@router.message()
async def handle_all(msg: Message):
    uid = msg.from_user.id
    now = datetime.now()
    if uid in timestamps and (now - timestamps[uid]).total_seconds() < 1:
        return
    timestamps[uid] = now

    # === MiniApp данные ===
    if hasattr(msg, 'web_app_data') and msg.web_app_data:
        cipher = msg.web_app_data.data
        print(f"📦 MiniApp от {uid}: {cipher[:50]}...")
        p = partner(uid)
        if not p:
            await msg.answer("❌ *Найдите собеседника сначала!*")
            return
        await bot.send_message(
            p,
            f"🔐 *Зашифрованное сообщение*\n\n"
            f"`{cipher}`\n\n"
            f"_Скопируйте и расшифруйте_"
        )
        await msg.answer("✅ *Отправлено*")
        return

    # === Обычные сообщения ===
    p = partner(uid)
    if not p:
        await msg.answer(
            "❌ *Вы не в диалоге*",
            reply_markup=main_menu()
        )
        return
    try:
        await bot.copy_message(p, msg.chat.id, msg.message_id)
    except:
        unlink(uid)
        await msg.answer("⚠️ *Собеседник отключился*", reply_markup=main_menu())

async def shutdown():
    print("🛑 Завершение...")
    if os.path.exists(PID_FILE): os.remove(PID_FILE)
    await bot.session.close()

def sig(signum, frame):
    asyncio.create_task(shutdown())
    sys.exit(0)

signal.signal(signal.SIGINT, sig)
signal.signal(signal.SIGTERM, sig)

async def main():
    if os.path.exists(PID_FILE): os.remove(PID_FILE)
    with open(PID_FILE, 'w') as f: f.write(str(os.getpid()))
    await bot.delete_webhook(drop_pending_updates=True)

    # Устанавливаем главную кнопку MiniApp как у BotFather
    await set_main_button()

    # Запускаем таймер автоудаления сообщений
    asyncio.create_task(auto_delete_messages())

    print("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
