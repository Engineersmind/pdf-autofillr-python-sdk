from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class BaseChunker(ABC):
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer
        logger.info(f"Initialized {self.__class__.__name__}")