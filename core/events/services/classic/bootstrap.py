"""Generate synthetic data for testing and development purposes."""
from typing import List
import random
from datetime import datetime
from mimesis import Person, Internet, Datetime
from mimesis import config as mimesis_config

from arxiv import taxonomy
from . import models

LOCALES = list(mimesis_config.SUPPORTED_LOCALES.keys())

def _get_locale() -> str:
    return LOCALES[random.randint(0, len(LOCALES) - 1)]


def _epoch(t: datetime) -> int:
    return int((t - datetime.utcfromtimestamp(0)).total_seconds())


LICENSES = [
    {
        "name": "",
        "note": None,
        "label": "None of the above licenses apply",
        "active": 1,
        "sequence": 99
    },
    {
        "name": "http://arxiv.org/licenses/assumed-1991-2003/",
        "note": "",
        "label": "Assumed arXiv.org perpetual, non-exclusive license to" +
                 " distribute this article for submissions made before" +
                 " January 2004",
        "active": 0,
        "sequence": 9
    },
    {
        "name": "http://arxiv.org/licenses/nonexclusive-distrib/1.0/",
        "note": "(Minimal rights required by arXiv.org. Select this unless" +
                " you understand the implications of other licenses.)",
        "label": "arXiv.org perpetual, non-exclusive license to distribute" +
                 " this article",
        "active": 1,
        "sequence": 1
    },
    {
        "name": "http://creativecommons.org/licenses/by-nc-sa/3.0/",
        "note": "",
        "label": "Creative Commons Attribution-Noncommercial-ShareAlike" +
                 " license",
        "active": 0,
        "sequence": 3
    },
    {
        "name": "http://creativecommons.org/licenses/by-nc-sa/4.0/",
        "note": "",
        "label": "Creative Commons Attribution-Noncommercial-ShareAlike" +
                 " license (CC BY-NC-SA 4.0)",
        "active": 1,
        "sequence": 7
    },
    {
        "name": "http://creativecommons.org/licenses/by-sa/4.0/",
        "note": "",
        "label": "Creative Commons Attribution-ShareAlike license" +
                 " (CC BY-SA 4.0)",
        "active": 1,
        "sequence": 6
    },
    {
        "name": "http://creativecommons.org/licenses/by/3.0/",
        "note": "",
        "label": "Creative Commons Attribution license",
        "active": 0,
        "sequence": 2
    },
    {
        "name": "http://creativecommons.org/licenses/by/4.0/",
        "note": "",
        "label": "Creative Commons Attribution license (CC BY 4.0)",
        "active": 1,
        "sequence": 5
    },
    {
        "name": "http://creativecommons.org/licenses/publicdomain/",
        "note": "(Suitable for US government employees, for example)",
        "label": "Creative Commons Public Domain Declaration",
        "active": 0,
        "sequence": 4
    },
    {
        "name": "http://creativecommons.org/publicdomain/zero/1.0/",
        "note": "",
        "label": "Creative Commons Public Domain Declaration (CC0 1.0)",
        "active": 1,
        "sequence": 8
    }
]

POLICY_CLASSES = [
    {"name": "Administrator", "class_id": 1, "description": ""},
    {"name": "Public user", "class_id": 2, "description": ""},
    {"name": "Legacy user", "class_id": 3, "description": ""}
]


def categories() -> List[models.CategoryDef]:
    """Generate data for current arXiv categories."""
    return [
        models.CategoryDef(
            category=category,
            name=data['name'],
            active=1
        ) for category, data in taxonomy.CATEGORIES.items()
    ]


def policy_classes() -> List[models.PolicyClass]:
    """Generate policy classes."""
    return [models.PolicyClass(**datum) for datum in POLICY_CLASSES]


def users(count: int = 500) -> List[models.User]:
    """Generate a bunch of random users."""
    _users = []
    for i in range(count):
        locale = _get_locale()
        person = Person(locale)
        net = Internet(locale)
        ip_addr = net.ip_v4()
        _users.append(models.User(
            first_name=person.name(),
            last_name=person.surname(),
            suffix_name=person.title(),
            share_first_name=1,
            share_last_name=1,
            email=person.email(),
            share_email=8,
            email_bouncing=0,
            policy_class=2,  # Public user.
            joined_date=_epoch(Datetime(locale).datetime()),
            joined_ip_num=ip_addr,
            joined_remote_host=ip_addr
        ))
    return _users


def licenses() -> List[models.License]:
    """Generate licenses."""
    return [models.License(**datum) for datum in LICENSES]
