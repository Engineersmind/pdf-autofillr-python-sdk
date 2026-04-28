from .base import BaseChunker
import logging

logger = logging.getLogger(__name__)

class WindowBasedChunker(BaseChunker):
    def __init__(self, tokenizer, prefix_threshold=10, suffix_threshold=10, lines_limit=40):
        super().__init__(tokenizer)
        self.prefix_threshold = prefix_threshold
        self.suffix_threshold = suffix_threshold
        self.lines_limit = lines_limit

    def build_fid_gid_window_map(self, extracted_data):
        gid_has_field = {}
        all_gids = []
        sgids = []

        for page in extracted_data["pages"]:
            for line in page["text_elements"]:
                gid = line["gid"]
                gid_has_field[gid] = False
                all_gids.append(gid)
                sgids.append(gid)
            for field in page["form_fields"]:
                fid_gid = field["gid"]
                gid_has_field[fid_gid] = True

        all_gids.sort()

        prev_true = {}
        last_true = -1
        for gid in all_gids:
            if gid_has_field.get(gid, False):
                last_true = gid
            prev_true[gid] = last_true

        next_true = {}
        next_t = -1
        for gid in reversed(all_gids):
            if gid_has_field.get(gid, False):
                next_t = gid
            next_true[gid] = next_t

        fid_window_map = {}
        for page in extracted_data["pages"]:
            for field in page["form_fields"]:
                fid = str(field["fid"])
                gid = field["gid"]
                start = gid - self.prefix_threshold
                end = gid + self.suffix_threshold
                fid_window_map[fid] = {"gid": gid, "window": (start, end)}

        return fid_window_map, sgids

    def chunk_fids_by_gid_context_linear(self, fid_window_map):
        fids = list(fid_window_map.keys())
        chunks = []
        current_fids = []
        current_gid_set = set()
        current_window_ranges = []

        i = 0
        while i < len(fids):
            fid = fids[i]
            win = fid_window_map[fid]["window"]
            new_gids = set(range(win[0], win[1] + 1))
            combined_gids = current_gid_set.union(new_gids)

            if len(combined_gids) <= self.lines_limit:
                current_fids.append(fid)
                current_window_ranges.append(win)
                current_gid_set = combined_gids
                i += 1
            else:
                chunks.append({"fids": current_fids, "window_ranges": current_window_ranges, "total_lines": len(current_gid_set)})
                current_fids = []
                current_window_ranges = []
                current_gid_set = set()

        if current_fids:
            chunks.append({"fids": current_fids, "window_ranges": current_window_ranges, "total_lines": len(current_gid_set)})

        return chunks

    def generate_context_and_stats(self, extracted_data, overlap=1):
        fid_window_map, _ = self.build_fid_gid_window_map(extracted_data)
        chunks = self.chunk_fids_by_gid_context_linear(fid_window_map)

        gid_to_line = {}
        for page in extracted_data["pages"]:
            for line in page["text_elements"]:
                gid_to_line[line["gid"]] = line["text"]

        result = {}
        for i, chunk in enumerate(chunks):
            chunk_gids = set()
            for start, end in chunk["window_ranges"]:
                chunk_gids.update(range(start, end + 1))

            sorted_gids = sorted(chunk_gids)
            text_lines = [gid_to_line[gid] for gid in sorted_gids if gid in gid_to_line]
            context_text = "\n".join(text_lines)

            fid_ints = [int(fid) for fid in chunk["fids"]]
            result[f"chunk_{i+1}"] = {
                "context": context_text,
                "start_fid": min(fid_ints) if fid_ints else -1,
                "end_fid": max(fid_ints) if fid_ints else -1,
                "gids": sorted_gids,
                "num_lines": len(text_lines)
            }

        return result, {}