"""
Logging configuration for the application.
Creates a Logs directory if it doesn't exist and sets up a rotating file handler and a stream handler.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

log_dirname = "Logs"
log_filename = "app.log"
log_filepath = os.path.join(os.getcwd(), log_dirname, log_filename)

os.makedirs(log_dirname, exist_ok=True)

if not os.path.exists(log_filepath):
    open(log_filepath, "w").close()

formatter = logging.Formatter('%(asctime)s | %(filename)s | %(lineno)s | %(levelname)s | %(message)s')

file_handler = RotatingFileHandler(log_filepath)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
stream_handler.setLevel(logging.INFO)

logger.addHandler(file_handler)
logger.addHandler(stream_handler)
