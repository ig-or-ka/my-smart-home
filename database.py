import os, asyncio
from datetime import datetime, timedelta
from enum import Enum, auto
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select



engine = create_async_engine("sqlite+aiosqlite:///files/db.sqlite3")
async_db_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class EventType(str, Enum):
    start = auto()
    ping = auto()
    hot = auto()
    cold = auto()


class MeterReading(Base):
    __tablename__ = "meter_readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[EventType]
    value: Mapped[int] = mapped_column(default=0)
    time: Mapped[datetime]


class DailyTask(Base):
    __tablename__ = "daily_task"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    desc: Mapped[str]
    everyday: Mapped[bool] = mapped_column(default=False)
    dtime: Mapped[datetime] = mapped_column(nullable=True)
    time: Mapped[timedelta] = mapped_column(nullable=True)


async def start_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    if not os.path.exists('files'):
        os.mkdir('files')

    asyncio.run(start_db())
