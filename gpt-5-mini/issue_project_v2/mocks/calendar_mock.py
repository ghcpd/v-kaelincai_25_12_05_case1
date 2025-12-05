from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import time

app = FastAPI()

class CreateRequest(BaseModel):
    request_id: str
    when: str
    details: dict

@app.post('/v1/calendar/create')
def create_calendar(req: CreateRequest, mode: str = 'ok'):
    if mode == 'delay':
        time.sleep(2)
    if mode == 'fail':
        raise HTTPException(status_code=500, detail='calendar error')
    return {"calendar_id": "cal_" + req.request_id, "status": "scheduled"}
