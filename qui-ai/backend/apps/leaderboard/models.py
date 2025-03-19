from sqlalchemy import Column, Integer, String, TIMESTAMP, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
import datetime
from pydantic import BaseModel

Base = declarative_base()

class Leaderboard(Base):
    __tablename__ = "leaderboard"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(String, nullable=False)
    username = Column(String, nullable=False)
    score = Column(Integer, nullable=False)
    timestamp = Column(TIMESTAMP, default=datetime.datetime.utcnow)

    __table_args__ = (UniqueConstraint("course_id", "username", name="unique_course_user"),)
# Pydantic Model
class LeaderboardEntry(BaseModel):
    course_id: str
    username: str
    score: int