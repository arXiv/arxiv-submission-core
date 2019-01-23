"""Helper functions."""

from functools import lru_cache as memoize

from arxiv.base.globals import get_application_config


@memoize(maxsize=1028)
def is_ascii(string: str) -> bool:
    """Determine whether or not a string is ASCII."""
    try:
        bytes(string, encoding='ascii')
        return True
    except UnicodeEncodeError:
        return False


def below_ascii_threshold(proportion: float) -> bool:
    """Whether or not the proportion of ASCII characters is too low."""
    threshold = get_application_config().get('TITLE_ASCII_THRESHOLD', 0.5)
    return proportion < threshold


@memoize(maxsize=1028)
def proportion_ascii(phrase: str) -> float:
    """Calculate the proportion of a string comprised of ASCII characters."""
    return len([c for c in phrase if is_ascii(c)])/len(phrase)
