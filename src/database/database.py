import os
import sqlite3
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from flask import Flask
from src.utils.config import config
from src.utils.logging_config import get_logger

logger = get_logger('database')

# Initialize SQLAlchemy
db = SQLAlchemy()

def _initialize_sqlite_db(db_path):
    """Initialize a new SQLite database file."""
    try:
        # Create a new SQLite database file
        conn = sqlite3.connect(db_path)
        conn.close()
        logger.info(f"Created new SQLite database at {db_path}")
    except Exception as e:
        logger.error(f"Error creating SQLite database: {str(e)}", exc_info=True)
        raise

def init_db(app):
    """Initialize the database with the Flask app."""
    try:
        database_url = config.get_database_url()
        logger.info("Initializing database with URL: %s", database_url)
        
        if database_url.startswith('sqlite:///'):
            # Extract the database path from the URL
            db_path = database_url.replace('sqlite:///', '')
            logger.info(f"Using SQLite database at: {db_path}")
            
            # Create the database directory if it doesn't exist
            db_dir = os.path.dirname(db_path)
            if not os.path.exists(db_dir):
                os.makedirs(db_dir)
                logger.info(f"Created database directory: {db_dir}")
            
            # If the database file doesn't exist or is empty, initialize it
            if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
                _initialize_sqlite_db(db_path)
                logger.info("Initialized new SQLite database file")
        
        # Configure SQLAlchemy
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Initialize the database with the app
        db.init_app(app)
        
        # Create all tables
        with app.app_context():
            # Import models to ensure they're registered with SQLAlchemy
            from .models import Device, MetricInfo, MetricValue
            
            # Log all tables that should be created
            for table in db.Model.metadata.tables.values():
                logger.info(f"Creating table: {table.name}")
            
            # Create all tables
            db.create_all()
            logger.info("Database tables created successfully")
            
            # Verify tables were created
            engine = db.get_engine()
            with engine.connect() as conn:
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                tables = [row[0] for row in result]
                logger.info(f"Existing tables in database: {tables}")
            
    except Exception as e:
        logger.error("Error initializing database: %s", str(e), exc_info=True)
        raise

def get_db():
    """Get a database session."""
    return db.session

def create_session():
    """Create a new database session."""
    database_url = config.get_database_url()
    engine = create_engine(database_url)
    
    # Configure SQLite for better concurrency
    if database_url.startswith('sqlite:///'):
        @event.listens_for(engine, 'connect')
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
    
    Session = sessionmaker(bind=engine)
    return Session()

def get_session():
    """Get a new database session."""
    return create_session()

def get_db_session():
    """Get a database session with automatic cleanup."""
    session = create_session()
    try:
        yield session
    finally:
        session.close()