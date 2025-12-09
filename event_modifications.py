from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.filters.state import StateFilter
from aiogram import Router, F, types
from aiogram.filters.command import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
from database import database as database_
import misc, sqlite3

dp = Router()
database = database_()

class EventModifyingStates(StatesGroup):
    idling = State()
    name = State()
    details = State()
    tour = State()

async def build_modification_message(state: FSMContext, step_id = 1, error_message = ""):
    data = await state.get_data()
    name = data.get("name", "[не указано]")
    desc = data.get("description", "[не указано]")
    tours_array = data.get("tours", list())

    tours_text = "[нет ни одного этапа]"
    if len(tours_array) > 0:
        cached = list()
        for i, tour_data in enumerate(tours_array, start = 1):
            cached.append(f"{i}) {tour_data.get('tour_name', 'TOUR_NAME')}\n{tour_data.get('start_date', datetime.now()).strftime('%d.%m.%Y')} - {tour_data.get('end_date', datetime.now()).strftime('%d.%m.%Y')}")
        
        tours_text = "\n\n".join(cached)


    builder_ = InlineKeyboardBuilder()
    builder_.button(text = "Название 📝", callback_data = "create_event_chna") # chna = change_name
    builder_.button(text = "Ссылка 📝", callback_data = "create_event_chli") # chli = change_link
    builder_.button(text = "+ Этап 📝", callback_data = "create_event_adto") # adto = add_tour
    builder_.button(text = "Отменить создание🛑", callback_data = "create_event_cncl") # cncl = cancel

    if (name != "[не указано]" and len(tours_array) > 0):
        builder_.button(text = "Создать событие ✅", callback_data = "create_event_sbmt") # sbmt = submit
    builder_.adjust(3, 1, 1)

    return f"<b><u>Админ Режим • Создание нового мероприятия</u></b>\n\n<blockquote>Название мероприятия: {name}\n\nЭтапы мероприятия:\n{tours_text}\n\nСсылка мерооприятия: {desc}</blockquote>\n\nДля добавления мероприятия укажите название и добавьте хотя бы один этап" + ("" if error_message == "" else ("\n\nУпс, ошибочка!\n" + error_message)), builder_.as_markup()

@dp.message(misc.AdminFilter(), Command("event_create"))
async def event_create_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    text, reply_markup = await build_modification_message(state)
    parential_message = await message.reply(
        text = text,
        parse_mode = "HTML", 
        reply_markup = reply_markup,
    )
    await state.update_data(parential_message_id = parential_message)

@dp.callback_query(F.data.startswith("create_event_"))
async def create_event_buttons(callback: types.CallbackQuery, state: FSMContext):
    suffix = callback.data.split("_")[-1]
    if suffix == "cncl":
        try: 
            await state.clear()
            await callback.message.edit_reply_markup(reply_markup = None)
            await callback.message.edit_text("Создание мероприятия отменено 🛑")
        except Exception as exp:
            pass
    elif suffix == "chna" or suffix == "chli" or suffix == "adto":
        builder_ = InlineKeyboardBuilder()
        builder_.button(text = "Назад 👈", callback_data = "create_event_back")
        builder_.button(text = "Отменить создание 🛑", callback_data = "create_event_cncl")

        await state.set_state(EventModifyingStates.name if suffix == "chna" else (EventModifyingStates.details if suffix == "chli" else EventModifyingStates.tour))
        await callback.message.edit_reply_markup(reply_markup = builder_.as_markup())
    elif suffix == "back":
        await state.set_state(EventModifyingStates.idling)
        text, reply_markup = await build_modification_message(state)
        await callback.message.edit_text(text, parse_mode = "HTML", reply_markup = reply_markup)
    elif suffix == "sbmt":
        data = await state.get_data()

        if data.get("name", '') == '' or len(data.get("tours", list())) < 1:
            await state.clear()
            await callback.message.edit_reply_markup(reply_markup = None)
            await callback.message.edit_text("Произошла ошибка. Пожалуйста, используйте /event_create повторно")
            return
        
        with database.get_cursor() as cursor:
            cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM events")
            event_id = cursor.fetchone()[0]
            cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM event_blocks")
            block_id = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO events (id, name, description)
                VALUES (%s, %s, %s)
            """, (event_id, data.get("name", "Unknown Name"), data.get("description", ""))) 

            for idx, tour_data in enumerate(data.get("tours", list())):
                cursor.execute("""
                    INSERT INTO event_blocks (id, event_id, start_date, end_date, name, description, link)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (block_id + idx, event_id, tour_data.get("start_date", datetime.now()), tour_data.get("end_date", datetime.now()), tour_data.get("tour_name", "Unknown Tour"), '', data.get("description", '')))
            
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup = None)
        await callback.message.reply("Меропрития успешно добавлено!")

@dp.message(misc.AdminFilter(), StateFilter(EventModifyingStates.tour), F.text)
async def event_create_tour(message: types.Message, state: FSMContext):
    try:
        data_array = message.text.split('\n')
        text = data_array[0]
        start_date = datetime.strptime(data_array[1], "%d.%m.%Y")
        end_date = datetime.strptime(data_array[2], "%d.%m.%Y")
        if start_date > end_date:
            await message.reply("Дата окончания не может быть раньше даты начала!")
        else:
            data = await state.get_data()
            tours_array = data.get("tours", [])
            tours_array.append({"tour_name": text, "start_date": start_date, "end_date": end_date})
            await state.update_data(tours = tours_array)      
    except Exception as exp:
        await message.reply("Неверный формат данных! Пример:\n\nБольшие Вызовы\n20.11.2025\n13.02.2026")
    
    state_data = await state.get_data()
    parential_message = state_data.get("parential_message_id")
    text, reply_markup = await build_modification_message(state)
    await parential_message.edit_text(text, parse_mode = "HTML", reply_markup = reply_markup)
    await message.delete()

@dp.message(misc.AdminFilter(), StateFilter(EventModifyingStates.name), F.text)
async def event_create_name(message: types.Message, state: FSMContext): 
    await state.update_data(name = message.text.strip())
    await state.set_state(EventModifyingStates.idling)

    state_data = await state.get_data()
    parential_message = state_data.get("parential_message_id")
    text, reply_markup = await build_modification_message(state)
    await parential_message.edit_text(text, parse_mode = "HTML", reply_markup = reply_markup)
    await message.delete()

@dp.message(misc.AdminFilter(), StateFilter(EventModifyingStates.details), F.text)
async def event_create_link(message: types.Message, state: FSMContext):
    await state.update_data(description = message.text)
    await state.set_state(EventModifyingStates.idling)
    
    state_data = await state.get_data()
    parential_message = state_data.get("parential_message_id")
    text, reply_markup = await build_modification_message(state)
    await parential_message.edit_text(text, parse_mode = "HTML", reply_markup = reply_markup)
    await message.delete()

