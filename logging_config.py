import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler

def setup_logging(log_level=logging.INFO):
    """
    Set up logging configuration for the application.
    
    Args:
        log_level: The logging level to use (default: logging.INFO)
    """
    # Create logs directory in user's home directory
    log_dir = Path.home() / '.py-plot' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure logging format
    log_format = '%(asctime)s.%(msecs)03d:%(levelname)s:%(name)s:%(message)s'
    date_format = '%Y%m%d_%H%M%S'  # YYYYMMDD_HHMMSS.sss (truncate microseconds to milliseconds)
    formatter = logging.Formatter(log_format, datefmt=date_format)
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all levels
    
    # File handler - captures all levels (DEBUG and above)
    log_file = log_dir / 'py-plot.log'
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,  # Keep 5 backup files
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)  # Capture all levels
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler - only INFO and above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # Only INFO and above
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Set specific loggers to WARNING level
    logging.getLogger('PyQt5').setLevel(logging.WARNING)
    logging.getLogger('pyqtgraph').setLevel(logging.WARNING)

def get_logger(name):
    """
    Get a logger instance for the given name.
    
    Args:
        name: The name for the logger (typically __name__)
        
    Returns:
        logging.Logger: A configured logger instance
    """
    return logging.getLogger(name) 