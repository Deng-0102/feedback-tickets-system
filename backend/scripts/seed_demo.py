from __future__ import annotations

import os

from sqlalchemy import select

import app.models  # noqa: F401
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models.enums import Role
from app.models.user import User


def main() -> None:
    if get_settings().app_env != "development":
        raise SystemExit("演示账号只能在开发环境初始化")
    password = os.getenv("DEMO_PASSWORD", "Demo123!")
    demo_users = [
        ("user001", "演示用户", Role.USER),
        ("agent001", "演示处理人员", Role.AGENT),
        ("admin", "系统管理员", Role.ADMIN),
    ]
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        for username, display_name, role in demo_users:
            exists = db.scalar(select(User).where(User.username == username))
            if exists:
                print(f"skip: {username}")
                continue
            db.add(
                User(
                    username=username,
                    display_name=display_name,
                    password_hash=hash_password(password),
                    role=role,
                )
            )
            print(f"created: {username} ({role.value})")
        db.commit()
    print("demo data ready; change the demo password before any shared deployment")


if __name__ == "__main__":
    main()

