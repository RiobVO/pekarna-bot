import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from database.models import Base

# На Railway автоматически задаётся DATABASE_URL для PostgreSQL.
# Локально используется SQLite.
_database_url = os.getenv("DATABASE_URL")

if _database_url:
    # Railway даёт URL вида postgres://... — меняем на asyncpg
    _database_url = _database_url.replace("postgres://", "postgresql+asyncpg://", 1)
else:
    _db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bakery.db")
    _database_url = f"sqlite+aiosqlite:///{os.path.normpath(_db_path)}"

engine = create_async_engine(_database_url)

session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_db():
    """Создаёт все таблицы в базе данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
