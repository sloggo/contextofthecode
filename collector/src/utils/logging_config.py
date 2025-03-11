import logging
import logging.handlers
import os
from typing import Optional
from .config import config

def setup_logger(name: str, log_file: Optional[str] = None) -> logging.Logger:
    """
    Set up a logger with both console and file handlers.
    
    Args:
        name: The name of the logger
        log_file: Optional custom log file path. If not provided, uses the default from config.
    
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(config.logging.level)
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file or config.logging.file_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    # Clear any existing handlers
    logger.handlers = []
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Create file handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file or config.logging.file_path,
        maxBytes=config.logging.max_size,
        backupCount=config.logging.backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(config.logging.level)
    file_handler.setFormatter(file_formatter)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(config.logging.level)
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    If the logger doesn't exist, it will be created with the default configuration.
    
    Args:
        name: The name of the logger
    
    Returns:
        logging.Logger: Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger = setup_logger(name)
    return logger

# Create default loggers for different components
web_logger = get_logger('web')
db_logger = get_logger('database')
collector_logger = get_logger('collector')
api_logger = get_logger('api') 