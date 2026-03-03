from aiogram import Router, F, types
from aiogram.filters.command import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import misc, sqlite3
from database import database as db
import random
from reminders import _set_reminder_target

database = db()
dp = Router()

def handle_new_user(message: types.Message): 
    connection = sqlite3.connect("local_storage.sql")
    cursor = connection.cursor()
    cursor.execute("SELECT chat_id FROM users WHERE chat_id = ?", (message.chat.id,))
    if cursor.fetchone() is None:
        print("Ура, новый юни юзэр!")
        cursor.execute("INSERT INTO users (chat_id, username) VALUES (?, ?)", (message.chat.id, message.chat.username))
        connection.commit()
    connection.close()

@dp.message(F.text, Command("start"))
async def start(message: types.Message):
    handle_new_user(message)

    builder = InlineKeyboardBuilder()
    builder.button(text = "💬 Наш канал", url = "https://t.me/it9tech")
    builder.button(text = "🌐 Наш сайт", url = "https://it9tech.ru")

    await message.answer(
        f"<strong>Добро пожаловать! 👋</strong>\nЯ - бот-ассистент команды айти актива\nОтвечу на Ваши вопросы, напомню о мероприятиях и многое другое!\n\nДля начала работы можно отправить свой вопрос в чат или использовать команду", 
        reply_markup = builder.as_markup(), parse_mode = "HTML"
    )

@dp.message(Command("events"))
async def events_cmd(message: types.Message): 
    with database.get_cursor() as cursor:
        cursor.execute("""
            SELECT
                eb.*,
                ev.name AS event_name
            FROM event_blocks eb
            LEFT JOIN events ev on ev.id = eb.event_id
            WHERE eb.start_date <= NOW() and eb.end_date >= NOW();
        """)
    
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        response = [dict(zip(columns, row)) for row in rows]
    
    if len(response) == 0:
        await message.answer(
            text = "Похоже, сейчас нет активных событий\nОтличная возможность отдохнуть!"
        )
    else:
        await message.answer(
            text = "<strong>🌟 Активные события на сегодня:</strong>\n\n" + "\n\n".join([f"<u>{b['event_name']} - {b['name']}</u>\n{b['start_date'].strftime('%d.%m.%Y')}-{b['end_date'].strftime('%d.%m.%Y')}" + (f"\n<a href=\"{b['link']}\">Ссылка на событие</a>" if b["link"] else '') for b in response]),
            parse_mode = "HTML", disable_web_page_preview = True
        )

from random import randint
@dp.message(Command("verify"))
async def verify_cmd(message: types.Message):
    await message.reply(f"Ваш код для верификации: <strong>{randint(1,9999):04d}</strong>", parse_mode = "HTML")

@dp.message(misc.AdminFilter(), Command("status"))
async def status_cmd(message: types.Message):
    connection = sqlite3.connect("local_storage.sql")
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")

    await message.reply(f"Всего пользоваетелей: <strong>{cursor.fetchone()[0]}</strong>", parse_mode = "HTML")

    connection.close()


@dp.message(misc.AdminFilter(), Command("event_target"))
async def event_target_cmd(message: types.Message):
    chat_id = message.chat.id
    thread_id = getattr(message, "message_thread_id", None) or 0

    _set_reminder_target(chat_id, thread_id)

    text = f"✔ Уведомления по мероприятиям будут отправляться сюда.\nChat ID: {chat_id}"
    if thread_id:
        text += f"\nThread ID: {thread_id}"

    await message.answer(text)

@dp.message(F.text.startswith("/"))
async def slash_handler(message: types.Message):
    if message.chat.type == "private":
        await message.answer(
            "<strong>Ой, ошибочка! 😔</strong>\nТакой команды не существует или она недоступна\nдля использования в данный момент.",
            parse_mode = "HTML"
        )

@dp.message(F.text)
async def process_text_message(message: types.Message):
    if message.chat.type != "private":
        return
    
    results = []
    for event in database.get_all_events_table():
        if event.get("name"):
            _, _, _, score = misc.similarity_score(message.text, event["name"])
            results.append((score, event))
    
    chosen = sorted(results, reverse=True, key=lambda x: x[0])[:min(3, len(results))]

    builder = InlineKeyboardBuilder()
    cb = lambda value: misc.with_callback_owner(value, message.from_user.id)
    for _, event in chosen:
        builder.button(text=event["name"], callback_data=cb(f"event_selecting:{event['id']}"))
    builder.button(text="Другое", callback_data=cb("event_selecting:other"))
    builder.adjust(1)

    await message.answer(
        text="<b>⭐️ Выберите мероприятие, которое Вас интересует</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )

rag_allowed = {"Большие вызовы"}

@dp.callback_query(F.data.startswith("event_selecting"))
async def show_event_card(callback: types.CallbackQuery):
    payload = await misc.get_owned_callback_payload(callback)
    if payload is None:
        return

    event_id = payload.split(':', 1)[1]
    
    with database.get_cursor() as cursor:
        cursor.execute("SELECT * FROM events WHERE id = %s", (event_id,))
        event_data = cursor.fetchone()
        event_columns = [column[0] for column in cursor.description]
        event = dict(zip(event_columns, event_data)) if event_data else None

        cursor.execute("SELECT * FROM event_blocks WHERE event_id = %s", (event_id,))
        blocks_data = cursor.fetchall()
        blocks_columns = [column[0] for column in cursor.description]
        blocks = [dict(zip(blocks_columns, row)) for row in blocks_data]
    
    builder = InlineKeyboardBuilder()
    cb = lambda value: misc.with_callback_owner(value, callback.from_user.id)
    builder.button(text = "🔔 Подписаться", callback_data=cb("event_subscribe"))
    
    if callback.message.chat.type == "private" and misc.is_admin(callback.message.chat.id):
        builder.button(text = "📝 Изменить", callback_data=cb(f"event_edit:{event_id}"))
        builder.button(text="🛑 Удалить", callback_data=cb(f"event_delete:{event_id}"))
        builder.adjust(1, 2)
    

    await callback.message.answer(
        text = f"<b>{event.get('name', 'Событие')}</b>",
        reply_markup = builder.as_markup(), parse_mode = "HTML"
    )
    await callback.message.delete()

@dp.callback_query(F.data.startswith("event_delete"))
async def event_delete_btn(callback: types.CallbackQuery):
    payload = await misc.get_owned_callback_payload(callback)
    if payload is None:
        return

    event_id = payload.split(':', 1)[1]

    with database.get_cursor() as cursor:
        cursor.execute("DELETE FROM event_blocks WHERE event_id = %s", (event_id,))
        cursor.execute("DELETE FROM events WHERE id = %s", (event_id,))
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(text = "🛑 Мероприятие успешно удалено")
