import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class DatabaseConfig:
    host: str
    port: int
    database: str
    user: str
    password: str
    use_sqlite: bool = True  # Default to SQLite for development

@dataclass
class LoggingConfig:
    level: str
    format: str
    file_path: str
    max_size: int  # in bytes
    backup_count: int

@dataclass
class CollectorConfig:
    collection_interval: int  # in seconds
    batch_size: int
    max_queue_size: int
    upload_interval: int  # in seconds

@dataclass
class WebConfig:
    host: str
    port: int
    debug: bool
    secret_key: str
    sse_interval: int  # in seconds

class Config:
    def __init__(self):
        # Database configuration
        self.db = DatabaseConfig(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', '5432')),
            database=os.getenv('DB_NAME', 'metrics_db'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres'),
            use_sqlite=os.getenv('USE_SQLITE', 'True').lower() == 'true'
        )

        # Logging configuration
        self.logging = LoggingConfig(
            level=os.getenv('LOG_LEVEL', 'INFO'),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            file_path=os.getenv('LOG_FILE', 'logs/app.log'),
            max_size=int(os.getenv('LOG_MAX_SIZE', '10485760')),  # 10MB
            backup_count=int(os.getenv('LOG_BACKUP_COUNT', '5'))
        )

        # Collector configuration
        self.collector = CollectorConfig(
            collection_interval=int(os.getenv('COLLECTION_INTERVAL', '60')),
            batch_size=int(os.getenv('BATCH_SIZE', '100')),
            max_queue_size=int(os.getenv('MAX_QUEUE_SIZE', '1000')),
            upload_interval=int(os.getenv('UPLOAD_INTERVAL', '5'))
        )

        # Web configuration
        self.web = WebConfig(
            host=os.getenv('APP_HOST', 'localhost'),
            port=int(os.getenv('APP_PORT', '8000')),
            debug=os.getenv('DEBUG', 'False').lower() == 'true',
            secret_key=os.getenv('SECRET_KEY', 'your-secret-key-here'),
            sse_interval=int(os.getenv('SSE_INTERVAL', '5'))
        )

    def get_database_url(self) -> str:
        """Get the database URL for SQLAlchemy."""
        if self.db.use_sqlite:
            # Use SQLite database in the instance folder
            db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../instance/metrics.db'))
            # Ensure the directory exists
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            # Convert Windows path to SQLite URL format
            db_url = f'sqlite:///{db_path.replace(os.sep, "/")}'
            return db_url
        else:
            # Use PostgreSQL
            return f"postgresql://{self.db.user}:{self.db.password}@{self.db.host}:{self.db.port}/{self.db.database}"

    def get_logging_config(self) -> dict:
        """Get logging configuration dictionary."""
        return {
            'level': self.logging.level,
            'format': self.logging.format,
            'file_path': self.logging.file_path,
            'max_size': self.logging.max_size,
            'backup_count': self.logging.backup_count
        }

    def get_collector_config(self) -> dict:
        """Get collector configuration dictionary."""
        return {
            'collection_interval': self.collector.collection_interval,
            'batch_size': self.collector.batch_size,
            'max_queue_size': self.collector.max_queue_size,
            'upload_interval': self.collector.upload_interval
        }

    def get_web_config(self) -> dict:
        """Get web configuration dictionary."""
        return {
            'host': self.web.host,
            'port': self.web.port,
            'debug': self.web.debug,
            'secret_key': self.web.secret_key,
            'sse_interval': self.web.sse_interval
        }

# Create a global config instance
config = Config() 