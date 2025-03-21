from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure the directories exist
data_dir = os.path.join(os.getcwd(), "data")
os.makedirs(data_dir, exist_ok=True)
logger.info(f"Data directory path: {data_dir}")

# Use an absolute path to avoid "unable to open database file" errors
DATABASE_PATH = os.path.join(os.getcwd(), "data", "rome.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
logger.info(f"Database path: {DATABASE_PATH}")
logger.info(f"Database URL: {DATABASE_URL}")

try:
    # Tạo engine
    logger.info("Creating database engine...")
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    
    # Test connection
    with engine.connect() as conn:
        logger.info("Database connection successful!")
    
    # Tạo sessionmaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("SessionLocal created successfully")

except Exception as e:
    logger.error(f"Database connection failed: {e}")
    raise

def get_db():
    """Get a database session"""
    try:
        db = SessionLocal()
        logger.debug("Database session created")
        yield db
    except Exception as e:
        logger.error(f"Error creating database session: {e}")
        raise
    finally:
        logger.debug("Closing database session")
        db.close()
        
def get_db_session():
    """Get a database session (non-generator version)"""
    try:
        db = SessionLocal()
        logger.debug("Database session created (non-generator)")
        return db
    except Exception as e:
        logger.error(f"Error creating database session (non-generator): {e}")
        raise