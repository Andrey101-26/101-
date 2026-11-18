"""Shared matching of plain-language queries against curated instructions."""

import re


def query_words(query):
    words = re.findall(r"[^\W_]+", query.casefold().replace("ё", "е"))
    filler = {"как", "в", "во", "на", "и", "с", "мне", "мой", "моем", "для", "где", "что", "если"}
    return [
        word for word in words
        if word not in filler and not word.startswith(("включ", "отключ", "настро", "запус", "запущ"))
    ]


def matches_query(words, keywords):
    terms = re.findall(r"[^\W_]+", keywords.casefold().replace("ё", "е"))
    return all(
        any(term.startswith(word) or (len(term) >= 4 and word.startswith(term)) for term in terms)
        for word in words
    )
