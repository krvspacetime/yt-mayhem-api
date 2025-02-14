from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from db.db import HistoryRecord


# SQLite engine and session
class HistoryRecordModel(BaseModel):
    video_id: str
    video_title: str
    channel_title: str


def create_history_record(db: Session, record: HistoryRecordModel):
    db_record = HistoryRecord(
        video_id=record.video_id,
        video_title=record.video_title,
        channel_title=record.channel_title,
        date=datetime.now(),
    )
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record
