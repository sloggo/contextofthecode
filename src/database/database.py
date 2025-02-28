import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from flask import Flask
from ..utils.config import get_settings

settings = get_settings()

# Get the absolute path to the database file
db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../instance/metrics.db'))
os.makedirs(os.path.dirname(db_path), exist_ok=True)

# Create the database URL
SQLALCHEMY_DATABASE_URI = f'sqlite:///{db_path}'

# Initialize Flask-SQLAlchemy
db = SQLAlchemy()

# Create the engine
engine = create_engine(SQLALCHEMY_DATABASE_URI)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_app(app: Flask):
    """Initialize the database with the Flask app"""
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    # Import models here to avoid circular imports
    from .models import Device, MetricInfo, MetricValue

    # Create tables
    with app.app_context():
        # Drop all tables first to ensure clean state
        db.drop_all()
        # Create all tables
        db.create_all()
        # Also create tables for SQLAlchemy (needed for FastAPI)
        init_db(app)

def init_db(app: Flask = None):
    """Initialize the database tables for both Flask-SQLAlchemy and SQLAlchemy"""
    from .models import Base
    
    if app:
        with app.app_context():
            Base.metadata.create_all(bind=engine)
    else:
        Base.metadata.create_all(bind=engine)

def get_db():
    """Get a database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 