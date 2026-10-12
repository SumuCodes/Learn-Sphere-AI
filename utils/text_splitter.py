# utils/text_splitter.py

def smart_split_text(text, chunk_size=8000, overlap=200):
    """
    Split text into chunks with a given overlap (in characters).
    Tries to cut at sentence boundaries (. ! ?) and avoids breaking words.
    """
    if overlap >= chunk_size:
        overlap = chunk_size // 4  # Guard against infinite loop

    chunks = []
    start = 0
    max_iterations = len(text) // max(1, chunk_size - overlap) + 10  # safety net

    while start < len(text) and max_iterations > 0:
        max_iterations -= 1
        end = min(start + chunk_size, len(text))

        if end < len(text):
            # Try to cut at sentence boundary (. ! ?) within the last half of the chunk
            search_start = max(start, end - chunk_size // 2)
            for delimiter in ('.', '!', '?'):
                pos = text.rfind(delimiter, search_start, end)
                if pos != -1:
                    end = pos + 1  # include the punctuation
                    break
            else:
                # No sentence boundary found – fall back to last space to avoid cutting a word
                last_space = text.rfind(' ', search_start, end)
                if last_space != -1:
                    end = last_space + 1

        chunks.append(text[start:end])
        start = end - overlap

    if max_iterations == 0 and start < len(text):
        # Safety: force the remainder as the last chunk
        chunks.append(text[start:])

    return chunks