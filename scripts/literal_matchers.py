"""Exact, case-preserving literal searches; no semantic judgments or shared cache."""
import re


def word(char):
    # Python Unicode str regex \w is alphanumeric or underscore.
    return char.isalnum() or char == '_'


def literal_find(text, value):
    if not value:
        return False
    left, right = word(value[0]), word(value[-1])
    start = 0
    while True:
        position = text.find(value, start)
        if position < 0:
            return False
        end = position + len(value)
        if ((not left or position == 0 or not word(text[position-1]))
                and (not right or end == len(text) or not word(text[end]))):
            return True
        start = position + 1


def make_matcher(strategy):
    if strategy == 'literal_find':
        return literal_find
    if strategy != 'compiled_regex':
        raise ValueError('Unknown literal lookup strategy')
    patterns = {}

    def contains(text, value):
        if not value:
            return False
        if value not in patterns:
            left = r'(?<!\w)' if word(value[0]) else ''
            right = r'(?!\w)' if word(value[-1]) else ''
            patterns[value] = re.compile(left + re.escape(value) + right)
        return patterns[value].search(text) is not None

    return contains
