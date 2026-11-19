import re

CJK = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]')
LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def cjk_count(s):
    return len(CJK.findall(s))


def latin_words(s):
    return len(LATIN_WORD.findall(s))


def word_count(s):
    cjk = cjk_count(s)
    latin = latin_words(s)
    return cjk + latin if cjk > latin else latin


def detect_language(s):
    cjk = cjk_count(s)
    latin = sum(c.isalpha() for c in s) - cjk
    return 'zh' if cjk > max(20, latin * 0.25) else 'en'


def first_sentences(s, limit=120):
    s = re.sub(r'\s+', ' ', s).strip()
    if len(s) <= limit:
        return s
    cut = s[:limit]
    pos = max(cut.rfind('. '), cut.rfind('! '), cut.rfind('? '), cut.rfind('。'), cut.rfind('！'))
    return (cut[:pos + 1] if pos > limit * 0.5 else cut).strip()
