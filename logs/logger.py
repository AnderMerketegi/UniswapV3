import os
import logging
from logging.handlers import RotatingFileHandler


class Logger:
    def __init__(self, log_dir='logs', log_file='logfile.log', max_size=1048576, backup_count=5):
        """
        Initializes the logger with automatic log file rotation.

        :param log_dir: The directory where the logs will be stored.
        :param log_file: The name of the log file.
        :param max_size: The maximum size of the log file in bytes before rotating (default: 1MB).
        :param backup_count: The number of backup log files to keep (default: 5).
        """
        self.log_dir = log_dir
        self.log_file = log_file
        self.max_size = max_size
        self.backup_count = backup_count
        self.logger = self._setup_logger()

    def _setup_logger(self):
        """Configure logger"""

        # Create the log directory if it doesn't exist
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        # Create the logger
        logger = logging.getLogger('AppLogger')
        logger.setLevel(logging.INFO)

        # Avoid adding multiple handlers
        if not logger.hasHandlers():
            # Log format: include date and time
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

            # RotatingFileHandler to handle log file rotation
            log_path = os.path.join(self.log_dir, self.log_file)
            handler = RotatingFileHandler(log_path, maxBytes=self.max_size, backupCount=self.backup_count)
            handler.setFormatter(formatter)

            # Add the handler to the logger
            logger.addHandler(handler)

        # Disable propagation to avoid logging messages twice
        logger.propagate = False

        return logger

    def info(self, message):
        """Method to log INFO level messages."""
        self.logger.info(message)

    def warning(self, message):
        """Method to log WARNING level messages."""
        self.logger.warning(message)

    def error(self, message):
        """Method to log ERROR level messages."""
        self.logger.error(message)
