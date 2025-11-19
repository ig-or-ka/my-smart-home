import asyncio
import config
import aiogram
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, CallbackQuery
import database
from database import select, MeterReading, EventType
from datetime import datetime, timedelta



class VARS:
    bot = aiogram.Bot(token=config.telegram_bot_token)
    loop: asyncio.AbstractEventLoop = None


def main_keyboard():
    keyboard = InlineKeyboardBuilder()

    keyboard.row(InlineKeyboardButton(
        text='Счетчики', 
        callback_data='meter_readings'
    ))

    return keyboard.as_markup()


def meters_keyboards():
    keyboard = InlineKeyboardBuilder()

    keyboard.row(InlineKeyboardButton(
        text='Обновить', 
        callback_data='meter_readings'
    ))
    keyboard.row(InlineKeyboardButton(
        text='Назад', 
        callback_data='main_menu'
    ))

    return keyboard.as_markup()


async def calculate_readings_msg():
    today = datetime.today()
    start_day = datetime(today.year, today.month, config.meter_start_day)
    start_month = datetime(today.year, today.month, 1)
    last_day_month = start_month - timedelta(days=1)

    if today.day < config.meter_start_day:
        start_day -= timedelta(days=last_day_month.day)
    
    end_day = start_day + timedelta(days=30)
    count_days = 30
    if end_day.day != start_day.day:
        end_day += timedelta(days=1)
        count_days += 1

    left_days = count_days - (end_day - today).days - 1
    msg = f'От {start_day.strftime('%d/%m/%Y')}\n'\
        f'Прошло {left_days}/{count_days} {round(left_days / count_days * 100, 2)}%\n\n'

    today = datetime(today.year, today.month, today.day)

    async with database.async_db_session() as session:
        async with session.begin():
            hot_today_sum = 0
            cold_today_sum = 0
            hot_month_sum = 0
            cold_month_sum = 0
            ping_time = 999

            ping_query = select(MeterReading).where(MeterReading.event_type == EventType.ping)
            ping_cur = await session.execute(ping_query)
            ping_obj = ping_cur.scalar()

            if ping_obj:
                ping_time = (datetime.now() - ping_obj.time).total_seconds()

            readings = select(MeterReading).where(
                MeterReading.time > start_day
            )
            readings = await session.execute(readings)

            for reading in readings.scalars():
                match reading.event_type:
                    case EventType.cold:
                        cold_month_sum += reading.value

                        if reading.time > today:
                            cold_today_sum += reading.value

                    case EventType.hot:
                        hot_month_sum += reading.value

                        if reading.time > today:
                            hot_today_sum += reading.value

    cold_square = round(cold_month_sum / 100, 3)
    hot_square = round(hot_month_sum / 100, 3)
    sum_month = round(cold_square+hot_square, 3)
    sum_day = cold_today_sum * 10 + hot_today_sum * 10
    msg += f'Контроллер: {'🟢' if ping_time < 120 else '🔴'} {round(ping_time)}с\n\n'\
        f'Месяц:\nНорма: {config.month_square_norm}к\n'\
        f'Использовано холодной: {cold_square}к\n'\
        f'Использовано горячей: {hot_square}к\n'\
        f'Сумма: {sum_month}к {round(sum_month / config.month_square_norm * 100, 2)}%\n\n'\
        f'День:\nНорма: {round(config.month_square_norm * 1000 / count_days)}л\n'\
        f'Использовано холодной: {cold_today_sum * 10}л\n'\
        f'Использовано горячей: {hot_today_sum * 10}л\n'\
        f'Сумма: {sum_day}л {round(sum_day / config.month_square_norm * count_days / 10, 2)}%'\

    return msg
   

user_router = aiogram.Router()


@user_router.message(CommandStart())
async def start_cmd(message: aiogram.types.Message):
    if message.from_user.id not in config.admin_id:
        return

    await message.answer('Меню', reply_markup=main_keyboard())


@user_router.callback_query()
async def _(callback: CallbackQuery):
    data = callback.data.split(':')

    match data[0]:
        case 'main_menu':
            await callback.message.edit_text('Меню', reply_markup=main_keyboard())

        case 'meter_readings':
            msg = await calculate_readings_msg()

            if msg == callback.message.text:
                await callback.answer('Нет обновлений!')
                return

            await callback.message.edit_text(msg, reply_markup=meters_keyboards())


async def main():
    VARS.loop = asyncio.get_running_loop()
    dp = aiogram.Dispatcher()
    dp.include_router(user_router)

    await dp.start_polling(VARS.bot)


if __name__ == "__main__":
    asyncio.run(main())