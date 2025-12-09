from aiogram import Router, F, types
from aiogram.filters.command import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import misc, sqlite3
from database import database as db

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


# Добавить в чекер, когда будет готов RAG-ассистент
# lambda message: message.text.startswith("/")
@dp.message()
async def slash_handler(message: types.Message):
    if message.chat.type == "private":
        await message.answer(
            "<strong>Ой, ошибочка! 😔</strong>\nТакой команды не существует или она недоступна\nдля использования в данный момент.",
            parse_mode = "HTML"
        )