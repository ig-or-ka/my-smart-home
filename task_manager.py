from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import DailyTask, select
import asyncio, database, datetime
from aiogram import Bot, types
import uuid, config



class VARS:
    scheduler = AsyncIOScheduler()
    bot: Bot = None
    done_tasks = set()
    sended_messenges = dict()
    task_jobs = dict()


async def day_task(task_info: DailyTask):
    start_moment = datetime.datetime.now()
    uuid_task = str(uuid.uuid4())

    while True:
        if datetime.datetime.now().day != start_moment.day:
            break

        if uuid_task in VARS.done_tasks:
            break

        keyboard = InlineKeyboardBuilder()
        keyboard.add(types.InlineKeyboardButton(
            text="Выполнено",
            callback_data=f"task_done:{uuid_task}"
        ))
        msg = await VARS.bot.send_message(
            task_info.user_id,
            task_info.desc,
            reply_markup=keyboard.as_markup()
        )
        msgs_ids = VARS.sended_messenges.setdefault(uuid_task, [])
        msgs_ids.append(msg.message_id)

        await asyncio.sleep(config.repet_task_time)


async def task_done(uuid_task, msg: types.Message):
    await msg.edit_text(msg.text + "\n\n✅ Задача выполнена!")

    if uuid_task not in VARS.sended_messenges:
        return

    VARS.done_tasks.add(uuid_task)
    msgs = VARS.sended_messenges[uuid_task]
    msgs.remove(msg.message_id)

    if len(msgs) > 0:
        await VARS.bot.delete_messages(msg.chat.id, msgs)
            

def new_task(task_info: DailyTask):
    if task_info.everyday:
        job = VARS.scheduler.add_job(
            day_task, 
            'cron', 
            args=(task_info,),
            day_of_week=task_info.day_of_week,
            hour=task_info.time.seconds // 3600,
            minute=task_info.time.seconds % 3600 // 60
        )

    else:
        job = VARS.scheduler.add_job(
            day_task,
            'date', 
            args=(task_info,),
            run_date=task_info.dtime
        )

    VARS.task_jobs[task_info.id] = job.id


def remove_task(task_id):
    if task_id in VARS.task_jobs:
        VARS.scheduler.remove_job(VARS.task_jobs[task_id])


async def init(bot: Bot):
    VARS.bot = bot
    VARS.scheduler.start()
    now = datetime.datetime.now()
    
    async with database.async_db_session() as session:
        async with session.begin():
            cur = await session.execute(select(DailyTask))

            for task in cur.scalars():
                if task.everyday or task.dtime > now:
                    new_task(task)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.create_task(init())
    loop.run_forever()