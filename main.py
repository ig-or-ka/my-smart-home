import asyncio
import config
import aiogram
from aiogram.enums import ParseMode 
from aiogram.filters import CommandStart, StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, CallbackQuery
import database
from sqlalchemy import delete
from database import select, MeterReading, EventType
from datetime import datetime, timedelta
import task_manager
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import BasicAuth
from aiogram.client.session.aiohttp import AiohttpSession



class FSM_User(StatesGroup):
    add_task = State()


class VARS:
    auth = BasicAuth(login=config.tg_proxy[0], password=config.tg_proxy[1])
    session = AiohttpSession(proxy=(f'http://{config.tg_proxy[2]}:{config.tg_proxy[3]}', auth))
    bot = aiogram.Bot(token=config.telegram_bot_token, session=session)
    loop: asyncio.AbstractEventLoop = None


def main_keyboard():
    keyboard = InlineKeyboardBuilder()

    keyboard.row(InlineKeyboardButton(
        text='Счетчики', 
        callback_data='meter_readings'
    ))
    keyboard.row(InlineKeyboardButton(
        text='Добавить задачу', 
        callback_data='add_task'
    ))
    keyboard.row(InlineKeyboardButton(
        text='Текущие задачи', 
        callback_data='current_tasks'
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


async def tasks_keyboard(user_id):
    keyboard = InlineKeyboardBuilder()
    now = datetime.now()

    async with database.async_db_session() as session:
        async with session.begin():
            cur = await session.execute(select(database.DailyTask))

            for task in cur.scalars():
                if task.user_id == user_id and (task.everyday or task.dtime > now):
                    if task.everyday:
                        text = f"{task.time.seconds // 3600}:{task.time.seconds % 3600 // 60} {task.desc}"

                        if task.day_of_week:
                            text = f"{task.day_of_week} {text}"

                    else:
                        text = f"{task.dtime.strftime("%H:%M %d.%m.%Y")} {task.desc}"

                    keyboard.row(InlineKeyboardButton(
                        text=text, 
                        callback_data=f'remove_task:{task.id}'
                    ))

    keyboard.row(InlineKeyboardButton(
        text='Назад', 
        callback_data='main_menu'
    ))

    return keyboard.as_markup()


def one_button_keyboard(text='Отмена', cdata='main_menu'):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(InlineKeyboardButton(
        text=text, 
        callback_data=cdata
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


@user_router.message(StateFilter(FSM_User.add_task))
async def _(message: aiogram.types.Message, state: FSMContext):
    await message.delete()
    data = await state.get_data()
    segs = message.text.split()
    wrong_format = True

    if len(segs) > 1:
        if '.' in segs[0] and ':' in segs[1]:
            if len(segs) > 2:
                now = datetime.now()
                try:
                    task_time = datetime.strptime(f"{segs[0]}.{now.year} {segs[1]}", "%d.%m.%Y %H:%M")
                except: pass
                else:
                    desc = message.text.replace(f"{segs[0]} {segs[1]} ", '')

                    async with database.async_db_session() as session:
                        async with session.begin():
                            task = database.DailyTask(
                                user_id=message.from_user.id,
                                desc=desc,
                                dtime=task_time
                            )
                            session.add(task)
                            await session.commit()
                            task_manager.new_task(task)

                    wrong_format = False

        elif ':' in segs[0]:
            try:
                time_segs = segs[0].split(':')
                task_time = timedelta(hours=int(time_segs[0]), minutes=int(time_segs[1]))
            except: pass
            else:
                desc = message.text.replace(f"{segs[0]} ", '')
                desc_segs = desc.split()
                
                day_of_week = None
                if desc_segs[0] in {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}:
                    day_of_week = desc_segs[0]
                    desc = desc.replace(f"{day_of_week} ", '')

                async with database.async_db_session() as session:
                    async with session.begin():
                        task = database.DailyTask(
                            user_id=message.from_user.id,
                            desc=desc,
                            everyday=True,
                            time=task_time,
                            day_of_week=day_of_week
                        )
                        session.add(task)
                        await session.commit()
                        task_manager.new_task(task)

                wrong_format = False

    if wrong_format:
        try:
            await VARS.bot.edit_message_text(
                "Неправильный формат",
                chat_id=message.chat.id,
                message_id=data['msg_id'],
                reply_markup=one_button_keyboard()
            )
        except: pass

    else:
        await state.clear()

        await VARS.bot.edit_message_text(
            "Задача успешно добавлена",
            chat_id=message.chat.id,
            message_id=data['msg_id'],
            reply_markup=one_button_keyboard("Готово")
        )


@user_router.callback_query()
async def _(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split(':')

    match data[0]:
        case 'main_menu':
            await state.clear()
            await callback.message.edit_text('Меню', reply_markup=main_keyboard())

        case 'meter_readings':
            msg = await calculate_readings_msg()

            if msg == callback.message.text:
                await callback.answer('Нет обновлений!')
                return

            await callback.message.edit_text(msg, reply_markup=meters_keyboards())

        case 'task_done':
            await task_manager.task_done(data[1], callback.message)

        case 'add_task':
            await state.set_state(FSM_User.add_task)
            await state.set_data({
                'msg_id':callback.message.message_id
            })

            txt = "Введите задание в формате:\n"\
                "<b>чч:mm *текст задания*</b> - если задание ежедневное\n"\
                "<b>чч:mm день_недели *текст задания*</b> - если задание ежедневное\n"\
                "<b>дд.mm чч:mm *текст задания*</b> - если задание одноразовое\n\n"\
                "Названия дней недели: <code>mon</code> <code>tue</code> <code>wed</code> <code>thu</code> <code>fri</code> <code>sat</code> <code>sun</code>"

            await callback.message.edit_text(
                txt, 
                reply_markup=one_button_keyboard(),
                parse_mode=ParseMode.HTML
            )

        case 'current_tasks':
            await callback.message.edit_text(
                "Выберите задачу для удаления", 
                reply_markup=await tasks_keyboard(callback.from_user.id)
            )

        case 'remove_task':
            async with database.async_db_session() as session:
                async with session.begin():
                    await session.execute(
                        delete(database.DailyTask)
                        .where(database.DailyTask.id == int(data[1])
                    )
                )
            task_manager.remove_task(int(data[1]))
                    
            await callback.message.edit_text(
                "Задача удалена", 
                reply_markup=one_button_keyboard("Готово")
            )


async def controller_checker_task():
    sended = False
    pred_ping_time = 999

    while True:
        ping_time = 999
        async with database.async_db_session() as session:
            async with session.begin():

                ping_query = select(MeterReading).where(MeterReading.event_type == EventType.ping)
                ping_cur = await session.execute(ping_query)
                ping_obj = ping_cur.scalar()

                if ping_obj:
                    ping_time = (datetime.now() - ping_obj.time).total_seconds()

        if ping_time > 60 and not sended:
            try:
                await VARS.bot.send_message(config.admin_id[0], 'Контроллер отключился!')
                sended = True
            except: pass

        if ping_time < pred_ping_time:
            sended = False

        pred_ping_time = ping_time

        await asyncio.sleep(60)


async def main():
    VARS.loop = asyncio.get_running_loop()
    dp = aiogram.Dispatcher()
    dp.include_router(user_router)

    VARS.loop.create_task(controller_checker_task())
    await task_manager.init(VARS.bot)
    await dp.start_polling(VARS.bot)


if __name__ == "__main__":
    asyncio.run(main())