from .base import BaseChunker
import logging

logger = logging.getLogger(__name__)

class PageBasedChunker(BaseChunker):
    def __init__(self, tokenizer, chunk_size, overlap):
        super().__init__(tokenizer)
        self.chunk_size = chunk_size
        self.overlap = overlap

    def get_page_chunk_context(self, extracted_data, start_page, end_page):
        total_pages = len(extracted_data["pages"])
        start_page = max(1, start_page)
        end_page = min(total_pages, end_page)
        combined_lines = []

        for page in extracted_data["pages"][start_page - 1 : end_page]:
            for line in page["text_elements"]:
                combined_lines.append(line["text"])

        combined_text = "\n".join(combined_lines)
        token_count = len(self.tokenizer.encode(combined_text))
        logger.info(f"Chunk Pages {start_page}-{end_page}: Tokens = {token_count}")
        return combined_text

    def generate_context_and_stats(self, extracted_data, overlap=None):
        overlap = self.overlap if overlap is None else overlap
        total_pages = len(extracted_data["pages"])
        context_dict = {}
        stats_dict = {}

        step = self.chunk_size - overlap
        i = 0
        chunk_id = 1

        while True:
            start_page = i * step + 1
            end_page = start_page + self.chunk_size - 1
            if start_page > total_pages:
                break
            end_page = min(end_page, total_pages)

            context_text = self.get_page_chunk_context(extracted_data, start_page, end_page)

            chunk_pages = extracted_data["pages"][start_page - 1:end_page]
            start_fids = []
            end_fids = []

            for page in chunk_pages:
                meta = page.get("metadata", {})
                if meta.get("start_fid", -1) >= 0 and meta.get("end_fid", -1) >= 0:
                    start_fids.append(meta["start_fid"])
                    end_fids.append(meta["end_fid"])

            min_fid = min(start_fids) if start_fids else -1
            max_fid = max(end_fids) if end_fids else -1

            key = f"Page {start_page}-{end_page}"
            context_dict[key] = {
                "context": context_text,
                "start_fid": min_fid,
                "end_fid": max_fid,
            }

            stats_dict[key] = (
                len(context_text.split()),
                sum(len(p["form_fields"]) for p in chunk_pages)
            )

            i += 1
            chunk_id += 1

        return context_dict, stats_dict