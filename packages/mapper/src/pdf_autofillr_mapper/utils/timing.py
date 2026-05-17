import time
import functools
import logging

logger = logging.getLogger(__name__)  

def timing_decorator(func):
    """Decorator to measure execution time of a function and log it."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()  # Start time
        result = func(*args, **kwargs)  # Execute function
        end_time = time.time()  # End time
        execution_time = end_time - start_time

        logger.info(f"Function '{func.__name__}' executed in {execution_time:.4f} seconds.")
        return result

    return wrapper
