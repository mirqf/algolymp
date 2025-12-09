from aiogram import Router, F, types
from aiogram.filters.command import Command
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.types.web_app_info import WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types.input_file import FSInputFile
from aiogram.filters.command import Command
import sqlite3, logging
from typing import Optional
from aiogram.filters.callback_data import CallbackData
import aiogram

whitelist = {5081716116, 778440498}

def get_userdata(message: types.Message):
    return (message.chat if message.chat.type == "private" else message.from_user)

class AdminFilter(aiogram.filters.BaseFilter):
    def __init__(self):
        super().__init__()
        
    async def __call__(self, message: types.Message) -> bool:
        # хардкод, заменить на запрос к бд
        return get_userdata(message).id in whitelist
