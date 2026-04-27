from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, Integer, DateTime, JSON, ForeignKey, text, func, select
from datetime import datetime, timedelta
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
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=True)


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
        # Migrate existing DBs gracefully
        for col_sql in [
            "ALTER TABLE users ADD COLUMN currency VARCHAR(8) DEFAULT 'USD'",
            "ALTER TABLE users ADD COLUMN last_seen DATETIME",
        ]:
            try:
                await conn.execute(text(col_sql))
            except Exception:
                pass  # Column already exists


async def get_or_create_user(tg_id: int, username: str = None) -> User:
    async with SessionLocal() as s:
        result = await s.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(tg_id=tg_id, username=username, last_seen=datetime.utcnow())
            s.add(user)
            await s.commit()
            await s.refresh(user)
        return user


async def touch_user(tg_id: int) -> None:
    """Update last_seen timestamp for presence tracking. Fire-and-forget."""
    try:
        async with SessionLocal() as s:
            result = await s.execute(select(User).where(User.tg_id == tg_id))
            user = result.scalar_one_or_none()
            if user:
                user.last_seen = datetime.utcnow()
                await s.commit()
    except Exception:
        pass  # Non-critical — never block the main flow


async def get_bot_stats(online_minutes: int = 5) -> dict:
    """Return total user count, online count, and today's active count."""
    async with SessionLocal() as s:
        # Total registered users
        total_res = await s.execute(select(func.count()).select_from(User))
        total = total_res.scalar() or 0

        # "Online" = last_seen within the last N minutes
        cutoff_online = datetime.utcnow() - timedelta(minutes=online_minutes)
        online_res = await s.execute(
            select(func.count()).select_from(User).where(User.last_seen >= cutoff_online))
        online = online_res.scalar() or 0

        # Active today = last_seen since midnight UTC
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_res = await s.execute(
            select(func.count()).select_from(User).where(User.last_seen >= today_start))
        today = today_res.scalar() or 0

    return {"total": total, "online": online, "today": today, "online_minutes": online_minutes}
