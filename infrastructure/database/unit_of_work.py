from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.database.session import AsyncSessionLocal


class UnitOfWork:
    """
    Manages a single DB transaction across multiple repositories.
    Subclass and add typed repository properties.

    Usage:
        async with UnitOfWork() as uow:
            await uow.products.add(entity)
            await uow.commit()
    """

    def __init__(self):
        self._session: AsyncSession | None = None

    async def __aenter__(self):
        self._session = AsyncSessionLocal()
        self._bind_repositories()
        return self

    async def __aexit__(self, exc_type, *_):
        if exc_type:
            await self.rollback()
        await self._session.close()

    @property
    def session(self) -> AsyncSession:
        return self._session

    async def commit(self):    await self._session.commit()
    async def rollback(self):  await self._session.rollback()
    async def refresh(self, o): await self._session.refresh(o)

    def _bind_repositories(self):
        """Override in subclasses to attach repository instances."""
        pass
