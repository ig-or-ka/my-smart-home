from fastapi import FastAPI, Request
from pydantic import BaseModel, Field
from datetime import datetime
import config
from database import (
    async_db_session, MeterReading, EventType, select
)

app = FastAPI()


class Item(BaseModel):
    type_event: str = Field(..., alias="type")
    value: int = Field(default=None)


@app.post("/counter_event/")
async def counter_event(request: Request, item: Item):
    if request.client.host != config.esp_host:
        return {'status':'error'}

    event_type = EventType[item.type_event]

    async with async_db_session() as session:
        async with session.begin():
            add_new = True
            if event_type == EventType.ping:
                query = select(MeterReading).where(MeterReading.event_type == EventType.ping)
                cur = await session.execute(query)
                ping_obj = cur.scalar()

                if ping_obj:
                    ping_obj.time = datetime.now()
                    add_new = False

            if add_new:
                session.add(MeterReading(
                    event_type=event_type,
                    value=item.value,
                    time=datetime.now()
                ))

    return {"status": "ok"}
