import logging
import sys
from datetime import datetime
import os

def setup_logger(name: str, log_level: int = logging.INFO) -> logging.Logger:
    """Set up a logger with consistent formatting and handlers"""
    
    # Create logs directory if it doesn't exist
    logs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../logs'))
    os.makedirs(logs_dir, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers = []
    
    # Create formatters
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Create file handler
    log_file = os.path.join(logs_dir, f'{name}_{datetime.now().strftime("%Y%m%d")}.log')
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    return logger 