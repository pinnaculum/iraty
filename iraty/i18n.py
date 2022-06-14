import re
from pathlib import Path

import iso639
from iso639.exceptions import InvalidLanguageValue


def lang_get(code: str):
    try:
        lang = iso639.Lang(code)
    except InvalidLanguageValue:
        pass
    else:
        return lang


def language_target(sourcep: Path):
    # Match ISO 639-1
    match = re.search(r'^(.*?)\.([a-z]{2})\.yaml$', sourcep.name)

    if match:
        lang = lang_get(match.group(2))
        if not lang:
            return match.group(1), None

        # check
        return match.group(1), lang

    match = re.search(r'(.*?)\.yaml$', sourcep.name)
    if match:
        return match.group(1), None

    return None, None
