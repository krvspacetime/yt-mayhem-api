from fastapi import APIRouter, Depends
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from db.db import get_db
from models.history import HistoryRecordModel, create_history_record
from schemas.schemas import HistoryRecord

router = APIRouter(prefix="/history", tags=["History"])


@router.get("/")
async def get_history(db: Session = Depends(get_db)):
    try:
        history_records = db.query(HistoryRecord).all()
        return {
            "message": "History records fetched successfully",
            "records": history_records,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/add/")
def add_history_record(record: HistoryRecordModel, db: Session = Depends(get_db)):
    try:
        new_record = create_history_record(db, record)
        return {
            "message": "History record added successfully",
            "record": new_record,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
