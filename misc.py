from aiogram import Router, F, types
import aiogram
from re import sub


whitelist = {5081716116, 778440498}
OWNER_MARKER = "::owner:"

def get_userdata(message: types.Message):
    return (message.chat if message.chat.type == "private" else message.from_user)

# хардкод, заменить на запрос к бд
def is_admin(user_id: int) -> bool:
    return user_id in whitelist

class AdminFilter(aiogram.filters.BaseFilter):
    def __init__(self):
        super().__init__()
        
    async def __call__(self, message: types.Message) -> bool:
        return is_admin(get_userdata(message).id)

def with_callback_owner(callback_data: str, user_id: int) -> str:
    return f"{callback_data}{OWNER_MARKER}{user_id}"


def parse_callback_owner(callback_data: str) -> tuple[str, int | None]:
    if OWNER_MARKER not in callback_data:
        return callback_data, None

    payload, owner_raw = callback_data.rsplit(OWNER_MARKER, 1)
    if not owner_raw.isdigit():
        return payload, None

    return payload, int(owner_raw)


async def get_owned_callback_payload(callback: types.CallbackQuery) -> str | None:
    payload, owner_id = parse_callback_owner(callback.data or "")

    if owner_id is None:
        await callback.message.edit_reply_markup(reply_markup = None)
        await callback.answer("Кнопка устарела. Откройте меню заново.", show_alert = True)
        return None

    return payload


def similarity_score(string, template):
    def normalize(text: str) -> str:
        text = text.lower().replace('ё', 'е')
        text = sub(r"[^a-zа-я0-9\s]", "", text)
        text = sub(r"\s+", " ", text).strip()
        return text

    def char_ngrams(text: str, n: int) -> set:
        return {text[i:i+n] for i in range(len(text) - n + 1)}
    
    def jaccard_similarity(a: set, b: set) -> float:
        if not a or not b:
            return 0.0
        intersection = len(a & b)
        union = len(a | b)
        return intersection / union
    
    string = normalize(string)
    template = normalize(template)
    return 0, 0, 0, jaccard_similarity(char_ngrams(string, 2), char_ngrams(template, 2))
