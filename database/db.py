from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, Integer, DateTime, JSON, Boolean, ForeignKey
from datetime import datetime
from config import DATABASE_URL


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[str] = mapped_column(String(64), nullable=True)
    bankroll: Mapped[float] = mapped_column(Float, default=100.0)
    profit_protection: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[str] = mapped_column(String(16), default="balanced")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Parlay(Base):
    __tablename__ = "parlays"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    target_odds: Mapped[float] = mapped_column(Float)
    total_odds: Mapped[float] = mapped_column(Float)
    stake: Mapped[float] = mapped_column(Float, default=0)
    selections: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/won/lost
    challenge_type: Mapped[str] = mapped_column(String(32), nullable=True)
    challenge_stage: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    settled_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_or_create_user(tg_id: int, username: str = None) -> User:
    async with SessionLocal() as s:
        from sqlalchemy import select
        result = await s.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(tg_id=tg_id, username=username)
            s.add(user)
            await s.commit()
            await s.refresh(user)
        return user
