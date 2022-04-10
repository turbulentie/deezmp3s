# -*- coding: utf-8 -*-
import os
import random
import re
import string
import unidecode


def clean(dirty_str):
    def _replace_va(match):
        if match.group(0)[0].isupper():
            return 'VA'
        return 'va'

    # tries to translate funky utf8 chars to their ascii equiv
    dirty_str = unidecode.unidecode(dirty_str)

    dirty_str = re.sub('@', 'at', dirty_str)
    dirty_str = re.sub('[+&]', 'and', dirty_str)
    dirty_str = re.sub(r'\$', 's', dirty_str)
    # important that this comes before the [ *=] regex
    dirty_str = re.sub(r'\s*-\s*', '-', dirty_str)
    dirty_str = re.sub(r'[ *=]', '_', dirty_str)
    dirty_str = re.sub(r'\.{2,}', '', dirty_str)
    dirty_str = re.sub(r'\[', '(', dirty_str)
    dirty_str = re.sub(']', ')', dirty_str)
    dirty_str = re.sub(r'[^a-zA-Z0-9_.()\-]', '', dirty_str)
    dirty_str = re.sub(
        'various_artists', _replace_va, dirty_str, flags=re.IGNORECASE
    )

    return dirty_str


def random_str():
    return ''.join([random.choice(string.hexdigits) for _ in range(6)])

