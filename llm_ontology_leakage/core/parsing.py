"""Turn raw model answers into identifier candidates"""

def normalize_answer(raw: str) -> str:
    """Remove surrounding whitespace"""
    return raw.strip()


def parse_elements(raw: str, list_valued: bool) -> list[str]:
    """Turn model output into a list of identifier candidates"""
    if not list_valued:
        return [normalize_answer(raw)]
    # comma split (other layouts count as wrong), and duplicates dropped for exact set matching
    return list(dict.fromkeys(normalize_answer(part) for part in raw.split(",")))
