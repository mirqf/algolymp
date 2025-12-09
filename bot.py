import asyncio, logging, sqlite3
from aiogram import Bot, Dispatcher

# Роутеры к сообщениям
from bot_commands import dp as router1
from event_modifications import dp as router2

async def main():
    bot = Bot(token = "")
    dp = Dispatcher()

    dp.include_router(router2)
    dp.include_router(router1)
    
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