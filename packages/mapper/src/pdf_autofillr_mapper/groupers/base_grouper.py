import logging

logger = logging.getLogger(__name__)

class BaseGrouper:
    def __init__(self, extracted_data: dict, **kwargs):
        self.extracted_data = extracted_data
        self.params = kwargs
        logger.info(f"Initialized {self.__class__.__name__}")

    def group(self):
        raise NotImplementedError("Subclasses must implement the group() method.")
