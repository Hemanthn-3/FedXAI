import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from backend.app.core.config import get_settings
from backend.app.models.hospital import Hospital
from backend.app.models.user import User
from backend.app.models.enums import UserRole
from backend.app.auth.security import hash_password

async def main():
    settings = get_settings()
    print("Database URL:", settings.database_url)
    
    engine = create_async_engine(settings.database_url, echo=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    hospitals_data = [
        {"name": "Hospital Node 1", "location": "Mumbai, India", "node_id": "hospital_1"},
        {"name": "Hospital Node 2", "location": "London, UK", "node_id": "hospital_2"},
        {"name": "Hospital Node 3", "location": "New York, USA", "node_id": "hospital_3"},
    ]
    
    async with async_session() as session:
        for hd in hospitals_data:
            # 1. Create or retrieve Hospital
            existing_hospital = await session.execute(
                select(Hospital).where(Hospital.node_id == hd["node_id"])
            )
            hospital = existing_hospital.scalar_one_or_none()
            if not hospital:
                hospital = Hospital(
                    id=uuid.uuid4(),
                    name=hd["name"],
                    location=hd["location"],
                    node_id=hd["node_id"],
                    status="online"
                )
                session.add(hospital)
                await session.flush()
                print(f"Created Hospital: {hospital.name} with ID {hospital.id}")
            else:
                print(f"Hospital already exists: {hospital.name}")
            
            # 2. Create scoped doctor user
            email = f"doctor@{hd['node_id']}.com"
            existing_user = await session.execute(
                select(User).where(User.email == email)
            )
            user = existing_user.scalar_one_or_none()
            if not user:
                user = User(
                    id=uuid.uuid4(),
                    name=f"Doctor for {hd['node_id']}",
                    email=email,
                    password_hash=hash_password("Doctor123!Doctor"),
                    role=UserRole.DOCTOR,
                    hospital_id=hospital.id,
                    is_active=True
                )
                session.add(user)
                await session.flush()
                print(f"Created Doctor: {user.email} scoped to {hospital.name}")
            else:
                print(f"Doctor already exists: {user.email}")
                
        await session.commit()
        print("Hospital and Doctor seeding completed successfully.")

if __name__ == "__main__":
    asyncio.run(main())
