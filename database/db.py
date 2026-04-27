import os
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Float,
    DateTime,
    ForeignKey,
    Boolean,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

DB_URL = os.getenv("DB_URL", "sqlite+aiosqlite:///parlay.db")

engine = create_async_engine(DB_URL, echo=False, future=True)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, unique=True, index=True)
    username = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    pref_risk = Column(String, default="balanced")
    pref_legs = Column(Integer, default=3)
    notify = Column(Boolean, default=True)


class Parlay(Base):
    __tablename__ = "parlays"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    risk = Column(String)
    total_odds = Column(Float)
    actual_odds = Column(Float, nullable=True)
    stake = Column(Float, default=0)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    settled_at = Column(DateTime, nullable=True)


class Selection(Base):
    __tablename__ = "selections"
    id = Column(Integer, primary_key=True)
    parlay_id = Column(Integer, ForeignKey("parlays.id"))
    fixture_id = Column(String)
    home = Column(String)
    away = Column(String)
    league = Column(String, nullable=True)
    market = Column(String)
    pick = Column(String)
    label = Column(String)
    odds = Column(Float)
    confidence = Column(Integer)
    kickoff = Column(String, nullable=True)
    result = Column(String, nullable=True)


def init_db():
    import asyncio

    async def _go():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_go())
