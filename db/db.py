from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime

from schemas.schemas import Base
from schemas.schemas import SearchRecord

# SQLite engine and session
DATABASE_URL = "sqlite:///./sqlite.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create database tables
Base.metadata.create_all(bind=engine)


# Db dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_search_record(db: Session, record: SearchRecord):
    db_record = SearchRecord(
        query=record.query,
        date=datetime.now(),
    )
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record
