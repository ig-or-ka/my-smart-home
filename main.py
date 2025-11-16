import asyncio
import config
import aiogram
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart



class VARS:
    bot = aiogram.Bot(token=config.telegram_bot_token)
    loop: asyncio.AbstractEventLoop = None


user_router = aiogram.Router()


@user_router.message(CommandStart())
async def start_cmd(message: aiogram.types.Message):
    if message.from_user.id not in config.admin_id:
        return

    await message.answer('<b>Hello!</b>', parse_mode=ParseMode.HTML)


async def main():
    VARS.loop = asyncio.get_running_loop()
    dp = aiogram.Dispatcher()
    dp.include_router(user_router)

    await dp.start_polling(VARS.bot)


if __name__ == "__main__":
    asyncio.run(main())