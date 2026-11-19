import re, json, sys
from textutil import word_count, detect_language, cjk_count


LIGATURES = {'\ufb00': 'ff', '\ufb01': 'fi', '\ufb02': 'fl', '\ufb03': 'ffi', '\ufb04': 'ffl',
             '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"'}


def normalize(text):
    for src, dst in LIGATURES.items():
        text = text.replace(src, dst)
    text = text.replace('\x0c', '\n\n').replace('\u00ad', '')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'(?<=[A-Za-z])-\s*\n\s*(?=[a-z])', '', text)
    return text


def clean_block(block):
    block = re.sub(r'[ \t]+', ' ', block).strip()
    block = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', block)
    return block


def split_blocks(text):
    blocks, cur = [], []
    for raw in normalize(text).split('\n'):
        line = raw.strip()
        if not line:
            if cur:
                blocks.append(' '.join(cur))
                cur = []
            continue
        if re.fullmatch(r'[\divxlIVXL]+', line):
            continue
        if re.fullmatch(r'(page\s*)?\d+', line, re.I):
            continue
        cur.append(line)
    if cur:
        blocks.append(' '.join(cur))
    return [b for b in (clean_block(x) for x in blocks) if b]


def split_sentences_en(text):
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in parts if p.strip()]


def split_sentences_zh(text):
    parts = re.split(r'(?<=[。！？!?])', text)
    return [p.strip() for p in parts if p.strip()]


def split_very_long(block, lang):
    n = word_count(block)
    if lang == 'en' and n <= 380:
        return [block]
    if lang == 'zh' and len(block) <= 2200:
        return [block]
    sents = split_sentences_en(block) if lang == 'en' else split_sentences_zh(block)
    limit = 220 if lang == 'en' else 700
    out, cur = [], []
    count = 0
    for s in sents:
        c = word_count(s)
        if cur and count + c > limit:
            out.append(' '.join(cur) if lang == 'en' else ''.join(cur))
            cur, count = [], 0
        cur.append(s)
        count += c
    if cur:
        out.append(' '.join(cur) if lang == 'en' else ''.join(cur))
    return out


def load_paragraphs_text(text):
    lang = detect_language(text)
    blocks = split_blocks(text)
    counts = {}
    for b in blocks:
        k = re.sub(r'\s+', ' ', b.lower())[:160]
        counts[k] = counts.get(k, 0) + 1
    out, seen = [], set()
    for b in blocks:
        k = re.sub(r'\s+', ' ', b.lower())[:160]
        if counts.get(k, 0) >= 3 and word_count(b) < 20:
            continue
        letters = sum(c.isalpha() for c in b)
        if word_count(b) < 12 and letters and sum(c.isupper() for c in b if c.isalpha()) / letters > 0.7:
            continue
        for piece in split_very_long(b, lang):
            piece = clean_block(piece)
            if word_count(piece) < 20:
                continue
            key = re.sub(r'\W+', '', piece.lower())[:120]
            if key in seen:
                continue
            seen.add(key)
            out.append(piece)
    return out


def load_paragraphs(path):
    raw = open(path, encoding='utf-8', errors='replace').read()
    return load_paragraphs_text(raw)


if __name__ == '__main__':
    ps = load_paragraphs(sys.argv[1] if len(sys.argv) > 1 else 'book.txt')
    print('paras', len(ps), 'language guess', detect_language(' '.join(ps[:20])))
    print('>=85 words:', sum(1 for p in ps if word_count(p) >= 85))
    print('40..84:', sum(1 for p in ps if 40 <= word_count(p) < 85))
    for p in ps[:3]:
        print('---', word_count(p))
        print(p[:300])
    json.dump(ps, open('paragraphs.json', 'w', encoding='utf-8'), ensure_ascii=False)
