from typing import List, Optional

from sqlalchemy import insert, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.customer import Customer


class EventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, client_id: str, description: str, file_name: Optional[str] = None) -> Event:
        event = Event(client_id=client_id, description=description, file_name=file_name)
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def create_with_customers(
        self,
        client_id: str,
        description: str,
        customers: List[Customer],
        file_name: Optional[str] = None,
    ) -> Event:
        event = Event(client_id=client_id, description=description, file_name=file_name)

        async with self.db.begin():
            self.db.add(event)
            await self.db.flush()

            for customer in customers:
                customer.event_id = event.id

            self.db.add_all(customers)

        await self.db.refresh(event)
        return event

    async def create_with_customer_records(
        self,
        client_id: str,
        description: str,
        customer_records: list[dict],
        file_name: Optional[str] = None,
        chunk_size: int = 1000,
    ) -> Event:
        event = Event(client_id=client_id, description=description, file_name=file_name)

        async with self.db.begin():
            self.db.add(event)
            await self.db.flush()

            for record in customer_records:
                record["event_id"] = event.id

            for start in range(0, len(customer_records), chunk_size):
                chunk = customer_records[start:start + chunk_size]
                await self.db.execute(insert(Customer), chunk)

        return event

    async def get_by_client(self, client_id: str) -> List[Event]:
        result = await self.db.execute(
            select(Event).where(Event.client_id == client_id).order_by(Event.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_with_customers_by_client(self, client_id: str) -> List[Event]:
        result = await self.db.execute(
            select(Event)
            .where(Event.client_id == client_id)
            .options(selectinload(Event.customers))
            .order_by(Event.created_at.asc(), Event.id.asc())
        )
        return list(result.scalars().unique().all())

    async def list_with_customers(self, client_id: Optional[str] = None) -> List[Event]:
        query = select(Event).options(selectinload(Event.customers))

        if client_id:
            query = query.where(Event.client_id == client_id)

        result = await self.db.execute(
            query.order_by(Event.client_id.asc(), Event.created_at.asc(), Event.id.asc())
        )
        return list(result.scalars().unique().all())

    async def get_with_customers(self, event_id: int) -> Optional[Event]:
        result = await self.db.execute(
            select(Event)
            .where(Event.id == event_id)
            .options(selectinload(Event.customers))
        )
        return result.scalar_one_or_none()

    async def bulk_insert_customers(self, customers: List[Customer]) -> None:
        self.db.add_all(customers)
        await self.db.commit()
