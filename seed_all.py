"""
FedPedia-XAI — Master Seed Script (Idempotent)
================================================
Run this once after every fresh Docker bring-up to ensure the database
has the correct hospitals, users, and a bootstrap global model.

Safe to run multiple times — uses upsert logic, never creates duplicates.

Usage (copy into container then run):
    docker cp seed_all.py fedpedia-backend:/app/seed_all.py
    docker exec fedpedia-backend python seed_all.py

Permanent Login Credentials
----------------------------
 Role            Email                        Password
 --------------- ---------------------------- --------------------
 hospital_admin  admin@fedpedia.com           FedAdmin@2025
 doctor          doctor.h1@fedpedia.com       DrNode1@2025
 doctor          doctor.h2@fedpedia.com       DrNode2@2025
 doctor          doctor.h3@fedpedia.com       DrNode3@2025
"""

import asyncio
import hashlib
import uuid
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.auth.security import hash_password
from backend.app.core.config import get_settings
from backend.app.models.enums import (
    DatasetType,
    ModelFramework,
    ModelSource,
    UserRole,
)
from backend.app.models.global_model import GlobalModel
from backend.app.models.hospital import Hospital
from backend.app.models.user import User

# ==============================================================================
#  PERMANENT CREDENTIALS  —  edit here if you ever want to change them
# ==============================================================================

HOSPITALS = [
    {"name": "Hospital Node 1", "location": "Mumbai, India",   "node_id": "hospital_1"},
    {"name": "Hospital Node 2", "location": "London, UK",      "node_id": "hospital_2"},
    {"name": "Hospital Node 3", "location": "New York, USA",   "node_id": "hospital_3"},
]

USERS = [
    # -- System admin -----------------------------------------------------------
    {
        "name":      "System Administrator",
        "email":     "sysadmin@fedpedia.com",
        "password":  "SysAdmin@2025",
        "role":      UserRole.SYSTEM_ADMIN,
        "node_id":   None,
    },
    # -- Admin -----------------------------------------------------------------
    {
        "name":      "Hospital Admin",
        "email":     "admin@fedpedia.com",
        "password":  "FedAdmin@2025",
        "role":      UserRole.HOSPITAL_ADMIN,
        "node_id":   "hospital_1",
    },
    # -- Doctors ---------------------------------------------------------------
    {
        "name":      "Dr. Arjun Mehta",
        "email":     "doctor.h1@fedpedia.com",
        "password":  "DrNode1@2025",
        "role":      UserRole.DOCTOR,
        "node_id":   "hospital_1",
    },
    {
        "name":      "Dr. Sarah Collins",
        "email":     "doctor.h2@fedpedia.com",
        "password":  "DrNode2@2025",
        "role":      UserRole.DOCTOR,
        "node_id":   "hospital_2",
    },
    {
        "name":      "Dr. James Carter",
        "email":     "doctor.h3@fedpedia.com",
        "password":  "DrNode3@2025",
        "role":      UserRole.DOCTOR,
        "node_id":   "hospital_3",
    },
]

# ==============================================================================


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def seed_hospitals(session) -> dict[str, Hospital]:
    """Upsert all hospitals; return a node_id -> Hospital map."""
    hospital_map: dict[str, Hospital] = {}
    for hd in HOSPITALS:
        result = await session.execute(
            select(Hospital).where(Hospital.node_id == hd["node_id"])
        )
        hospital = result.scalar_one_or_none()
        if hospital is None:
            hospital = Hospital(
                id=uuid.uuid4(),
                name=hd["name"],
                location=hd["location"],
                node_id=hd["node_id"],
                status="online",
            )
            session.add(hospital)
            await session.flush()
            print(f"  [+] Created  hospital: {hospital.name}")
        else:
            print(f"  [=] Exists   hospital: {hospital.name}")
        hospital_map[hd["node_id"]] = hospital
    return hospital_map


async def seed_users(session, hospital_map: dict[str, Hospital]) -> None:
    """Upsert all users — update password/name if already present."""
    for ud in USERS:
        hospital = hospital_map[ud["node_id"]] if ud["node_id"] else None
        result = await session.execute(
            select(User).where(User.email == ud["email"])
        )
        user = result.scalar_one_or_none()
        new_hash = hash_password(ud["password"])
        if user is None:
            user = User(
                id=uuid.uuid4(),
                name=ud["name"],
                email=ud["email"],
                password_hash=new_hash,
                role=ud["role"],
                hospital_id=hospital.id if hospital else None,
                is_active=True,
            )
            session.add(user)
            await session.flush()
            print(f"  [+] Created  user: {user.email!r:40s} role={ud['role'].value}")
        else:
            user.name = ud["name"]
            user.password_hash = new_hash
            user.is_active = True
            await session.flush()
            print(f"  [=] Updated  user: {user.email!r:40s} role={ud['role'].value}")


async def seed_model(session) -> None:
    """Train and seed the bootstrap heart-disease federated model with fitted StandardScaler."""
    from train_bootstrap_model import (
        build_datasets,
        evaluate_model,
        load_combined_dataset,
        save_artifact,
        train_model,
    )

    print("\n  [Training bootstrap model from hospital node CSVs...]")
    df = load_combined_dataset()
    x_train_sc, x_test_sc, y_train, y_test, scaler, _, _ = build_datasets(df)
    model = train_model(x_train_sc, y_train, x_test_sc, y_test)
    metrics = evaluate_model(model, x_test_sc, y_test)
    model_path = save_artifact(model, scaler, metrics)
    checksum = _sha256(model_path)
    version = "federated-heart_disease-r0001-bootstrap"

    # Deactivate all previous federated heart-disease models
    await session.execute(
        update(GlobalModel)
        .where(
            GlobalModel.dataset_type == DatasetType.HEART_DISEASE,
            GlobalModel.source == ModelSource.FEDERATED,
        )
        .values(is_active=False)
    )

    result = await session.execute(
        select(GlobalModel).where(GlobalModel.version == version)
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        session.add(
            GlobalModel(
                id=uuid.uuid4(),
                version=version,
                path=str(model_path),
                checksum_sha256=checksum,
                dataset_type=DatasetType.HEART_DISEASE,
                framework=ModelFramework.PYTORCH,
                source=ModelSource.FEDERATED,
                metrics=metrics,
                is_active=True,
            )
        )
        print(f"  [+] Created  global model: {version}")
    else:
        existing.path = str(model_path)
        existing.checksum_sha256 = checksum
        existing.metrics = metrics
        existing.is_active = True
        print(f"  [=] Updated  global model: {version}")


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        print("\n-- Hospitals -------------------------------------------------")
        hospital_map = await seed_hospitals(session)

        print("\n-- Users -----------------------------------------------------")
        await seed_users(session, hospital_map)

        print("\n-- Global Model ----------------------------------------------")
        await seed_model(session)

        await session.commit()

    print()
    print()
    print("=" * 68)
    print("  FedPedia-XAI  —  Active Login Credentials")
    print("=" * 68)
    print(f"  {'ROLE':<16} {'EMAIL':<34} {'PASSWORD'}")
    print(f"  {'-'*16} {'-'*34} {'-'*20}")
    for u in USERS:
        print(f"  {u['role'].value:<16} {u['email']:<34} {u['password']}")
    print("=" * 68)
    print()


if __name__ == "__main__":
    asyncio.run(main())
