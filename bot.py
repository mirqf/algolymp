import asyncio, logging, sqlite3
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
import os

# Роутеры к сообщениям
from bot_commands import dp as router1
from event_modifications import dp as router2

load_dotenv()

async def main():
    bot = Bot(token = os.getenv("BOT_TOKEN"))
    dp = Dispatcher()

    dp.include_router(router2)
    dp.include_router(router1)

    # запускаем таск напоминаний
    from reminders import reminder_worker
    asyncio.create_task(reminder_worker(bot))
    
    #await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":

    connection = sqlite3.connect("local_storage.sql")
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            username TEXT,
            admin BOOLEAN DEFAULT FALSE
        )
    """)
    connection.commit()
    connection.close()

    print("Successfully launched!")
    asyncio.run(main())