#!/usr/bin/env python3
"""
Initialize database schema and create admin user.
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, create_admin_user
from loguru import logger


async def main():
    """Initialize database and create admin user."""
    try:
        # Initialize schema and pgvector
        logger.info("Initializing database schema...")
        await init_db()
        
        # Create default admin user
        logger.info("Creating admin user...")
        await create_admin_user(
            username="admin",
            password="admin123",  # Change this in production!
            email="admin@medical-ai.local"
        )
        
        logger.info("✅ Database initialization complete!")
        logger.warning("⚠️  Default admin credentials: username=admin, password=admin123")
        logger.warning("⚠️  Change the password immediately in production!")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
