"""Script to create admin user."""

import asyncio
import sys

from vkt_bot.core.repositories.user import CreateUserSchema, UserRepository
from vkt_bot.core.security import get_password_hash
from vkt_bot.db.session import async_session


async def create_admin_user(username: str, password: str, email: str) -> None:
    """Create admin user."""
    async with async_session() as session:
        user_repo = UserRepository(session)

        # Check if user already exists
        existing = await user_repo.get_or_none(username)
        if existing:
            print(f"User '{username}' already exists!")
            return

        # Create admin user
        create_schema = CreateUserSchema(
            username=username,
            hashed_password=get_password_hash(password),
            email=email,
            is_active=True,
            is_superuser=True,
        )

        user = await user_repo.create(create_schema, commit=True)
        print(f"Admin user '{user.username}' created successfully!")


def main() -> None:
    """Main entry point."""
    if len(sys.argv) != 4:
        print("Usage: uv run python -m vkt_bot.scripts.create_admin <username> <password> <email>")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]
    email = sys.argv[3]

    asyncio.run(create_admin_user(username, password, email))


if __name__ == "__main__":
    main()
