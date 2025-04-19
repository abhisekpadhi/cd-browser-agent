import logging
import os
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

class ThreadedLogger:
    def __init__(self):
        self.logger = logging.getLogger('threaded_logger')
        self.logger.setLevel(logging.INFO)
        
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        # Create file handler
        log_file = f'logs/app_{datetime.now().strftime("%Y%m%d")}.log'
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        # Create formatter that only outputs the message
        formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(file_handler)
        
        # Create thread pool for logging
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="logger")

    def _log_message(self, level, message, data=None):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        log_entry = {
            "timestamp": timestamp,
            "level": level.upper(),
            "message": message
        }
        if data:
            log_entry.update(data)
        getattr(self.logger, level)(json.dumps(log_entry))

    def info(self, message, data=None):
        self.executor.submit(self._log_message, 'info', message, data)
        
    def error(self, message, data=None):
        self.executor.submit(self._log_message, 'error', message, data)
        
    def warning(self, message, data=None):
        self.executor.submit(self._log_message, 'warning', message, data)
        
    def debug(self, message, data=None):
        self.executor.submit(self._log_message, 'debug', message, data)

# Create singleton instance
log = ThreadedLogger()

# if __name__ == "__main__":
#     log.info("Hello, How are you doing!", {"user": "test", "action": "greeting"})
#     # # Give some time for the log to be written
#     # from time import sleep
#     # sleep(0.1)
