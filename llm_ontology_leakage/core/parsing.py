"""Turn raw model answers into identifier candidates"""

from .config import IdFormat

def normalize_answer(raw: str) -> str:
    """Remove surrounding whitespace"""
    return raw.strip()


def parse_elements(raw: str, list_valued: bool) -> list[str]:
    """Turn model output into a list of identifier candidates"""
    if not list_valued:
        return [normalize_answer(raw)]
    # comma split (other layouts count as wrong), and duplicates dropped for exact set matching
    return list(dict.fromkeys(normalize_answer(part) for part in raw.split(",")))


def matches_format(raw: str, list_valued: bool, fmt: IdFormat) -> bool:
    """Check whether the model answer is written in the given id_format"""
    candidates = parse_elements(raw, list_valued)

    def one(c: str) -> bool:
        if fmt == "full":
            return "://" in c
        if fmt == "prefix":
            return ":" in c and "://" not in c
        return ":" not in c  # plain
    return bool(candidates) and all(one(c) for c in candidates)
