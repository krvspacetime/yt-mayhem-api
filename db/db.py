from sqlalchemy import create_engine, Column, String, Integer, Enum, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from ..models.downloads import DownloadStatus

Base = declarative_base()


# Database model for download tracking
class Download(Base):
    __tablename__ = "downloads"
    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=True)
    quality = Column(String, nullable=True)
    output_dir = Column(String, nullable=True)
    status = Column(Enum(DownloadStatus), nullable=False)
    downloaded_bytes = Column(Integer, nullable=True, default=0)
    total_bytes = Column(Integer, nullable=True)
    stage = Column(String, nullable=True)


class HistoryRecord(Base):
    __tablename__ = "history"
    id = Column(Integer, primary_key=True)
    video_id = Column(String, nullable=False)
    video_title = Column(String, nullable=False)
    channel_title = Column(String, nullable=False)
    date = Column(DateTime, nullable=False)


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
