from .page_chunker import PageBasedChunker
from .window_chunker import WindowBasedChunker
import logging

logger = logging.getLogger(__name__)

def get_chunker(strategy_name, tokenizer, **kwargs):

    logger.info(f"Initializing chunker strategy: {strategy_name}")
    logger.info(f"Chunker parameters: {kwargs}")

    if strategy_name == "page":
        return PageBasedChunker(
            tokenizer,
            chunk_size=kwargs.get("chunk_size"),
            overlap=kwargs.get("overlap"),
        )
    elif strategy_name == "window":
        return WindowBasedChunker(
            tokenizer,
            prefix_threshold=kwargs.get("prefix_threshold", 10),
            suffix_threshold=kwargs.get("suffix_threshold", 10),
            lines_limit=kwargs.get("lines_limit", 400),
        )
    else:
        raise ValueError(f"Unknown chunking strategy: {strategy_name}")



def get_chunkers_from_config(strategy_list, tokenizer):
    chunkers = []
    for strategy_cfg in strategy_list:
        strategy_name = strategy_cfg.get("name")
        if not strategy_name:
            raise ValueError("Missing 'name' in chunking strategy config.")
        chunker = get_chunker(strategy_name, tokenizer, **strategy_cfg)
        chunkers.append(chunker)
    return chunkers
