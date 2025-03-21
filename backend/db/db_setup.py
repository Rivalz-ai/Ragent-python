import os
import sys
import logging
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from models import Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger('db_setup')

# Get database path from environment or use default
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///data/rome.db")

# Fix: Correctly create sync URL from async URL
if DATABASE_URL.startswith("sqlite+aiosqlite:"):
    # Take only the path part after the third slash
    path_part = DATABASE_URL.split("sqlite+aiosqlite:///")[1]
    # Create proper SQLite URL
    sync_url = f"sqlite:///{path_part}"
    logger.info(f"Converted async URL to sync URL: {sync_url}")
else:
    sync_url = DATABASE_URL
    logger.info(f"Using database URL as is: {sync_url}")

# Extract file path from DATABASE_URL
if "sqlite" in DATABASE_URL:
    parts = DATABASE_URL.split("///")
    if len(parts) > 1:
        db_path = parts[1]  # This gets everything after ///
    else:
        db_path = "data/rome.db"  # Default if parsing fails
else:
    db_path = "data/rome.db"  # Default for non-sqlite URLs

logger.info(f"Database path: {db_path}")

# Create parent directories if they don't exist
os.makedirs(os.path.dirname(db_path), exist_ok=True)

def setup_database():
    try:
        logger.info(f"Creating database engine with URL: {sync_url}")
        engine = create_engine(sync_url)
        
        # Check if database file exists
        db_exists = os.path.exists(db_path)
        
        if not db_exists:
            logger.info(f"Creating new database at {db_path}")
            # Create all tables
            Base.metadata.create_all(engine)
            logger.info("Database tables created successfully")
            
            # Set permissions for container environment
            try:
                os.chmod(db_path, 0o666)
                logger.info("Set database file permissions to 666")
            except Exception as e:
                logger.warning(f"Could not set permissions: {e}")
        else:
            logger.info(f"Database already exists at {db_path}")
            
            # Verify tables
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()
            expected_tables = Base.metadata.tables.keys()
            
            # Check for missing tables
            missing_tables = set(expected_tables) - set(existing_tables)
            if missing_tables:
                logger.info(f"Creating missing tables: {missing_tables}")
                Base.metadata.create_all(engine, checkfirst=True)
            else:
                logger.info("All required tables exist")
                
        return 0
    except Exception as e:
        logger.error(f"Database setup failed: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit_code = setup_database()
    sys.exit(exit_code)