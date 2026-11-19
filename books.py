import os, sys, json, re, shutil, sqlite3, subprocess, tempfile, time, urllib.request, html
import runtime
import haoce_api as api
import paras as para_lib
from textutil import detect_language, word_count

BOOKS = os.path.join(runtime.APP, 'books')
WORK = os.path.join(runtime.APP, 'work')
CDN = 'https://cdn.haoce.com'
GUT_MIRROR = 'https://mirrors.xmission.com/gutenberg'
GUT_INDEX_URL = GUT_MIRROR + '/GUTINDEX.ALL'
TAG_RE = re.compile(r'<[^>]+>')
UA = ('Mozilla/5.0 (Linux; Android 15; PGZ110) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/120.0.6099.230 Mobile Safari/537.36')
DEFAULT_TARGETS = {'topic': 2, 'reply': 10, 'langdu': 30, 'zhaichao': 15, 'report': 1}
DEFAULT_MIN = {'langdu': 30, 'zhaichao': 20, 'insight': 25, 'reply': 25, 'report': 100}


def book_dir(book_id):
    return os.path.join(BOOKS, str(int(book_id)))


def work_dir(book_id):
    return os.path.join(WORK, str(int(book_id)))


def meta_path(book_id):
    return os.path.join(book_dir(book_id), 'meta.json')


def pdf_path(book_id):
    return os.path.join(book_dir(book_id), 'book.pdf')


def txt_path(book_id):
    return os.path.join(book_dir(book_id), 'book.txt')


def paragraphs_path(book_id):
    return os.path.join(book_dir(book_id), 'paragraphs.json')


def read_json(path, default=None):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _int(v):
    try:
        return int(v or 0)
    except Exception:
        return 0


def short_title(title):
    t = re.sub(r'\s+', ' ', title or '').strip()
    if not t:
        return '这本书'
    runs = re.findall(r"[A-Za-z][A-Za-z0-9'’:,.\-]*(?:\s+[A-Za-z0-9'’:,.\-]+){1,}", t)
    if runs:
        best = max(runs, key=lambda x: len(x.split())).strip(' .,:;-–—')
        if len(best.split()) >= 2:
            return best
    return t


def _meta_from_detail(bid, d):
    b = d.get('book') or {}
    j = d.get('bookJoin') or {}
    o = d.get('book_opt') or {}
    title = (b.get('book') or '').strip() or f'书籍 {bid}'
    joined = any(j.get(k) is not None for k in ('topic_cnt', 'comment_cnt', 'tag_3_cnt', 'tag_5_cnt', 'tag_6_cnt'))
    return {
        'book_id': int(bid),
        'title': title,
        'short_title': short_title(title),
        'author': (b.get('book_writer') or '').strip(),
        'pdf': (b.get('book_pdf') or '').strip(),
        'pages': _int(b.get('book_page')),
        'words': _int(b.get('book_word_cnt')),
        'targets': {'topic': _int(b.get('user_topic')), 'reply': _int(b.get('user_comment')),
                    'langdu': _int(b.get('tag_3_config')), 'zhaichao': _int(b.get('tag_6_config')),
                    'report': _int(b.get('tag_5_config'))},
        'min_words': {'langdu': _int(o.get('word_3')), 'zhaichao': _int(o.get('word_6')),
                      'insight': _int(b.get('word_topic')), 'reply': _int(b.get('word_comment')),
                      'report': _int(o.get('word_5'))},
        'joined': joined,
        'stub': False,
        'updated': int(time.time()),
    }


def _fill_meta(m):
    m.setdefault('short_title', short_title(m.get('title')))
    m.setdefault('author', '')
    m.setdefault('pdf', '')
    m.setdefault('targets', dict(DEFAULT_TARGETS))
    m.setdefault('min_words', dict(DEFAULT_MIN))
    m.setdefault('joined', False)
    m.setdefault('language', '')
    return m


def meta(book_id=None, refresh=False, progress=None):
    bid = int(book_id or api.active_book_id())
    cached = read_json(meta_path(bid))
    if cached and not refresh and not cached.get('stub'):
        return _fill_meta(cached)
    try:
        fresh = _meta_from_detail(bid, api.book_detail(bid))
    except Exception:
        if cached:
            cached['offline'] = True
            return _fill_meta(cached)
        raise
    if cached:
        for k in ('language', 'novel_id', 'paragraph_count', 'library_at', 'legacy'):
            if cached.get(k) and not fresh.get(k):
                fresh[k] = cached[k]
    write_json(meta_path(bid), fresh)
    return _fill_meta(fresh)


def cached_meta(book_id=None):
    cfg = api.load_cfg()
    bid = int(book_id or cfg.get('book_id') or 0)
    if bid <= 0:
        return {}
    return _fill_meta(read_json(meta_path(bid), {}) or {})


def update_meta(book_id, **kw):
    bid = int(book_id)
    m = read_json(meta_path(bid), {}) or {'book_id': bid}
    m.update(kw)
    write_json(meta_path(bid), m)
    return m


def _download(url, dest, progress=print, timeout=180):
    if url.startswith('//'):
        url = 'https:' + url
    elif not url.startswith('http'):
        url = CDN + url
    part = dest + '.part'
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Referer': 'https://appclient.haoce.com/'})
    progress('下载 PDF：' + url)
    with urllib.request.urlopen(req, timeout=timeout) as r, open(part, 'wb') as f:
        total = _int(r.headers.get('Content-Length'))
        got, mark = 0, 0
        while True:
            chunk = r.read(262144)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if got - mark > 2097152:
                mark = got
                if total:
                    progress('已下载 %.1f/%.1f MB' % (got / 1048576, total / 1048576))
                else:
                    progress('已下载 %.1f MB' % (got / 1048576))
    if os.path.getsize(part) < 10000:
        os.remove(part)
        raise RuntimeError('PDF 下载不完整')
    os.replace(part, dest)
    size = os.path.getsize(dest)
    progress('PDF 已保存（%s）' % ('%.1f MB' % (size / 1048576) if size >= 1048576 else '%d KB' % (size // 1024)))


def _placeholder_hint(pages):
    if pages and pages <= 2:
        return '好策给这本书的 PDF 只有 %d 页（电子版使用说明），不是正文' % pages
    return 'PDF 文本提取失败（可能是扫描版），请改用 TXT 导入'


def _extract_pdf(pdf, txt, progress=print):
    exe = runtime.find_pdftotext(api.load_cfg())
    if exe:
        progress('提取文本：pdftotext')
        r = subprocess.run([exe, '-enc', 'UTF-8', pdf, txt], capture_output=True, timeout=300,
                           creationflags=runtime.NO_WINDOW)
        if r.returncode == 0 and os.path.exists(txt) and os.path.getsize(txt) > 1000:
            return 'pdftotext'
        progress('pdftotext 失败，改用 pypdf：' + (r.stderr or b'').decode('utf-8', 'replace')[:120])
    try:
        from pypdf import PdfReader
    except Exception:
        raise RuntimeError('找不到 pdftotext：请把 pdftotext.exe 和三个 DLL 放入 bin/，或安装 pypdf')
    progress('提取文本：pypdf')
    reader = PdfReader(pdf)
    pages = []
    for i, page in enumerate(reader.pages):
        try:
            pages.append(page.extract_text() or '')
        except Exception:
            pages.append('')
        if i and i % 50 == 0:
            progress('已解析 %d/%d 页' % (i, len(reader.pages)))
    text = '\n\n'.join(pages)
    with open(txt, 'w', encoding='utf-8') as f:
        f.write(text)
    if len(text) < 1000:
        raise RuntimeError(_placeholder_hint(len(reader.pages)))
    return 'pypdf'


def _build_from_text(bid, progress=print):
    txt = txt_path(bid)
    raw = open(txt, encoding='utf-8', errors='replace').read()
    ps = para_lib.load_paragraphs(txt)
    if len(ps) < 10:
        raise RuntimeError('提取到的段落太少（%d 段，%d 字符），请改用 TXT 导入' % (len(ps), len(raw)))
    write_json(paragraphs_path(bid), ps)
    lang = detect_language(' '.join(ps[:40]))
    update_meta(bid, language=lang, paragraph_count=len(ps), library_at=int(time.time()))
    progress('段落库已生成：%d 段，语言 %s' % (len(ps), lang))
    return {'book_id': bid, 'paragraphs': len(ps), 'language': lang, 'chars': len(raw)}


def _novel_fields(novel):
    # 章节接口要的是整个 novel 对象，按 jQuery 的深层序列化提交，传 id 会返回 222
    fields = {}
    for k, v in (novel or {}).items():
        if isinstance(v, dict):
            for k2, v2 in v.items():
                fields['novel[%s][%s]' % (k, k2)] = str(v2)
        elif isinstance(v, list):
            for i, v2 in enumerate(v):
                fields['novel[%s][%d]' % (k, i)] = str(v2)
        else:
            fields['novel[%s]' % k] = str(v)
    return fields


def _clean_html(s):
    return re.sub(r'\s+', ' ', html.unescape(TAG_RE.sub('', s or ''))).strip()


def _from_reader_api(bid, novel_id, progress=print):
    if not novel_id:
        raise RuntimeError('缺少 novel_id')
    progress('从好策阅读器接口取正文：novel_id=%d' % int(novel_id))
    rep = api.request('/book/novel/listV2?id=%d&book_id=%d' % (int(novel_id), int(bid)))
    if rep.get('error'):
        raise RuntimeError('listV2 失败：%s(%s)' % (rep.get('error_des'), rep.get('error')))
    data = rep.get('data') or {}
    nov = data.get('novel') or {}
    novel = nov.get('novel') or {}
    chapters = nov.get('chapter') or []
    if not chapters:
        raise RuntimeError('接口未返回章节')
    fields = _novel_fields(novel)
    fields['book_id'] = str(int(bid))
    lines = []
    for i, cp in enumerate(chapters, 1):
        cp_id = cp.get('cp_id')
        if not cp_id:
            continue
        try:
            r2 = api.request('/book/novel/chapter/%s' % cp_id, fields)
        except Exception as e:
            progress('  第 %d/%d 章请求失败：%s' % (i, len(chapters), e))
            continue
        if r2.get('error'):
            progress('  第 %d/%d 章返回错误 %s，跳过' % (i, len(chapters), r2.get('error')))
            continue
        ch = (r2.get('data') or {}).get('chapter') or {}
        title = _clean_html(ch.get('title'))
        if title:
            lines.append('\n' + title + '\n')
        for it in ch.get('contents') or []:
            if it.get('type') and it.get('type') != 'text':
                continue
            if str(it.get('lg') or '').lower() == 'cn':
                continue
            t = _clean_html(it.get('text'))
            if t:
                lines.append(t)
        progress('  已取 %d/%d 章（%d 段）' % (i, len(chapters), len(lines)))
    raw = '\n\n'.join(lines)
    if len(raw) < 1000:
        raise RuntimeError('阅读器接口返回的正文过少（%d 字符）' % len(raw))
    os.makedirs(book_dir(bid), exist_ok=True)
    with open(txt_path(bid), 'w', encoding='utf-8') as f:
        f.write(raw)
    progress('接口正文已保存：%d 字符' % len(raw))
    return _build_from_text(bid, progress)


STOPWORDS = {'the', 'and', 'for', 'with', 'from', 'vol', 'part', 'book', 'novel'}


def _gut_id_candidates(title):
    t = re.sub(r'[^a-z0-9 ]', ' ', (title or '').lower())
    t = re.sub(r'\s+', ' ', t).strip()
    if not t:
        return []
    words = [w for w in t.split(' ') if len(w) > 2 and w not in STOPWORDS]
    return words[:6]


def _from_gutenberg(bid, title, progress=print):
    progress('尝试从 Gutenberg 镜像按书名找公版全文…')
    req = urllib.request.Request(GUT_INDEX_URL, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            index = r.read().decode('utf-8', 'replace')
    except Exception as e:
        raise RuntimeError('无法下载 Gutenberg 索引：%s' % e)
    words = _gut_id_candidates(title)
    if not words:
        raise RuntimeError('书名里没有可用于检索的英文词')
    hits = []
    for line in index.split('\n'):
        low = line.lower()
        if not all(w in low for w in words):
            continue
        mm = re.search(r'\s(\d{1,6})\s*$', line)
        if not mm:
            continue
        hits.append((len(line), int(mm.group(1)), line.strip()))
    if not hits:
        raise RuntimeError('Gutenberg 索引中没有匹配《%s》的公版书' % (title or ''))
    hits.sort()
    gid = hits[0][1]
    s = str(gid)
    url = '%s/%s/%s/%s-0.txt' % (GUT_MIRROR, '/'.join(s[:-1]) or '0', s, s)
    progress('命中 Gutenberg #%d：%s' % (gid, hits[0][2][:80]))
    progress('下载：' + url)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            raw = r.read().decode('utf-8', 'replace')
    except Exception as e:
        raise RuntimeError('下载 Gutenberg 全文失败（镜像可能未同步该书）：%s' % e)
    m1 = re.search(r'\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG[^\n]*\*\*\*', raw)
    if m1:
        raw = raw[m1.end():]
    m2 = re.search(r'\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG[^\n]*\*\*\*', raw)
    if m2:
        raw = raw[:m2.start()]
    if len(raw) < 1000:
        raise RuntimeError('Gutenberg 全文过短')
    os.makedirs(book_dir(bid), exist_ok=True)
    with open(txt_path(bid), 'w', encoding='utf-8') as f:
        f.write(raw)
    progress('Gutenberg 全文已保存：%d 字符' % len(raw))
    res = _build_from_text(bid, progress)
    update_meta(bid, text_source='gutenberg:%d' % gid)
    return res



def _novel_id_for(bid):
    m = read_json(meta_path(bid)) or {}
    nid = _int(m.get('novel_id'))
    if nid > 0:
        return nid
    cfg = api.load_cfg()
    if _int(cfg.get('book_id')) == int(bid):
        return _int(cfg.get('novel_id'))
    return 0


def ensure_library(book_id=None, progress=print, force=False):
    bid = int(book_id or api.active_book_id())
    cached = read_json(paragraphs_path(bid))
    if cached and len(cached) >= 10 and not force:
        m = cached_meta(bid)
        return {'book_id': bid, 'paragraphs': len(cached), 'language': m.get('language', ''),
                'cached': True}
    if cached and len(cached) < 10 and not force:
        progress('现有段落库只有 %d 段，重新构建…' % len(cached))
    os.makedirs(book_dir(bid), exist_ok=True)
    m = meta(bid, refresh=force)
    if os.path.exists(txt_path(bid)) and not force:
        try:
            res = _build_from_text(bid, progress)
            res['cached'] = False
            return res
        except RuntimeError as e:
            progress('已有 book.txt 不可用（%s），改用其他来源' % e)
    errors = []

    nid = _novel_id_for(bid)
    if nid > 0:
        try:
            res = _from_reader_api(bid, nid, progress)
            update_meta(bid, novel_id=nid, text_source='reader_api')
            res['cached'] = False
            return res
        except Exception as e:
            errors.append('阅读器接口：%s' % e)
            progress('阅读器接口取文失败：%s' % e)
    else:
        errors.append('阅读器接口：缺少 novel_id（请先点“读取当前书籍”）')

    pdf = pdf_path(bid)
    try:
        if not os.path.exists(pdf) or force:
            if not m.get('pdf'):
                raise RuntimeError('详情接口没有给出 PDF')
            _download(m['pdf'], pdf, progress)
        _extract_pdf(pdf, txt_path(bid), progress)
        res = _build_from_text(bid, progress)
        update_meta(bid, text_source='pdf')
        res['cached'] = False
        return res
    except Exception as e:
        errors.append('好策 PDF：%s' % e)
        progress('好策 PDF 取文失败：%s' % e)

    try:
        res = _from_gutenberg(bid, m.get('short_title') or m.get('title'), progress)
        res['cached'] = False
        return res
    except Exception as e:
        errors.append('Gutenberg 镜像：%s' % e)
        progress('Gutenberg 镜像取文失败：%s' % e)

    raise RuntimeError('三条取文途径都失败，请用“导入文本”手动选择 TXT/PDF。\n' + '\n'.join(errors))


def import_file(path, book_id=None, progress=print):
    bid = int(book_id or api.active_book_id())
    if not os.path.exists(path):
        raise RuntimeError('文件不存在：' + path)
    os.makedirs(book_dir(bid), exist_ok=True)
    ext = os.path.splitext(path)[1].lower()
    m = read_json(meta_path(bid)) or {}
    if not m:
        try:
            m = meta(bid)
        except Exception:
            m = {'book_id': bid, 'title': os.path.splitext(os.path.basename(path))[0],
                 'short_title': os.path.splitext(os.path.basename(path))[0], 'author': '',
                 'targets': dict(DEFAULT_TARGETS), 'min_words': dict(DEFAULT_MIN),
                 'joined': False, 'stub': True}
            write_json(meta_path(bid), m)
    if ext == '.pdf':
        shutil.copy2(path, pdf_path(bid))
        progress('已导入 PDF：' + os.path.basename(path))
        _extract_pdf(pdf_path(bid), txt_path(bid), progress)
    elif ext in ('.txt', '.md', '.text'):
        shutil.copy2(path, txt_path(bid))
        progress('已导入文本：' + os.path.basename(path))
    else:
        raise RuntimeError('只支持 .txt / .md / .pdf')
    return _build_from_text(bid, progress)


def paragraphs(book_id=None):
    bid = int(book_id or api.active_book_id())
    ps = read_json(paragraphs_path(bid))
    if ps and len(ps) >= 10:
        return ps
    ensure_library(bid)
    return read_json(paragraphs_path(bid), [])


def status(book_id=None):
    bid = int(book_id or api.active_book_id())
    m = cached_meta(bid)
    ps = read_json(paragraphs_path(bid)) or []
    return {'book_id': bid, 'title': m.get('title', ''), 'short_title': m.get('short_title', ''),
            'author': m.get('author', ''), 'targets': m.get('targets', dict(DEFAULT_TARGETS)),
            'min_words': m.get('min_words', dict(DEFAULT_MIN)), 'joined': m.get('joined'),
            'language': m.get('language', ''), 'paragraphs': len(ps),
            'has_pdf': os.path.exists(pdf_path(bid)), 'has_txt': os.path.exists(txt_path(bid))}


def current_book(progress=print):
    cfg = api.load_cfg()
    adb = runtime.find_adb(cfg)
    if not adb:
        raise RuntimeError('找不到 adb：把 adb.exe 放进 bin/，或在 config.json 里配置 adb 路径')
    serial = runtime.pick_serial(adb, cfg)
    remote = '/sdcard/haoce_dcstorage_%d.db' % os.getpid()
    tmp = os.path.join(tempfile.gettempdir(), 'haoce_dcstorage_%d.db' % os.getpid())
    try:
        subprocess.run([adb, '-s', serial, 'root'], capture_output=True, timeout=40,
                       creationflags=runtime.NO_WINDOW)
        time.sleep(1.2)
        subprocess.run([adb, '-s', serial, 'wait-for-device'], capture_output=True, timeout=40,
                       creationflags=runtime.NO_WINDOW)
        cp = subprocess.run([adb, '-s', serial, 'shell', 'cp',
                             '/data/data/app.haoce.com/databases/DCStorage', remote],
                            capture_output=True, text=True, errors='replace', timeout=60,
                            creationflags=runtime.NO_WINDOW)
        pull = subprocess.run([adb, '-s', serial, 'pull', remote, tmp],
                              capture_output=True, text=True, errors='replace', timeout=60,
                              creationflags=runtime.NO_WINDOW)
        if pull.returncode != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) < 1000:
            msg = ((cp.stderr or '') + (pull.stderr or '') + (cp.stdout or '')).strip()
            raise RuntimeError('读取 DCStorage 失败（需要 adb root）：' + msg[:160])
        con = sqlite3.connect(tmp)
        try:
            tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
            candidates = []
            for table in tables:
                q = '"' + table.replace('"', '""') + '"'
                try:
                    cols = [r[1] for r in con.execute('pragma table_info(' + q + ')')]
                    if 'key' not in cols or 'value' not in cols:
                        continue
                    has_ts = 'timestamp' in cols
                    rows = con.execute('select key, value' + (', timestamp' if has_ts else '') + ' from ' + q).fetchall()
                except Exception:
                    continue
                for row in rows:
                    key, value = row[0], row[1]
                    if isinstance(key, bytes):
                        key = key.decode('utf-8', 'replace')
                    ts = str(row[2] or '') if has_ts else ''
                    if key != '_winExtras' and 'Extras' not in str(key):
                        continue
                    if isinstance(value, bytes):
                        value = value.decode('utf-8', 'replace')
                    try:
                        obj = json.loads(value)
                    except Exception:
                        continue
                    detail = obj.get('detail') or obj.get('data', {}).get('detail') or {}
                    bid = _int(detail.get('book_id') or obj.get('book_id'))
                    if bid <= 0:
                        for s in (detail.get('url'), obj.get('url'), detail.get('id'), obj.get('id')):
                            mm = re.search(r'[?&]book_id=(\d+)', str(s or ''))
                            if mm:
                                bid = int(mm.group(1))
                                break
                    if bid <= 0:
                        continue
                    novel_id = _int(detail.get('novel_id') or obj.get('novel_id'))
                    if not novel_id:
                        for r in rows:
                            mm = re.match(r'book_(\d+)_', str(r[0]))
                            if mm:
                                novel_id = int(mm.group(1))
                                break
                    info = {'book_id': bid, 'novel_id': novel_id,
                            'title': detail.get('title') or '', 'url': detail.get('url') or obj.get('url') or ''}
                    candidates.append((ts, len(candidates), info))
            if candidates:
                best = max(candidates, key=lambda x: (x[0], x[1]))[2]
                ids = sorted({c[2]['book_id'] for c in candidates})
                if len(ids) > 1:
                    progress('检测到多本书的页面记录 %s，按最近访问时间选择 book_id=%d' % (ids, best['book_id']))
                progress('当前阅读：%s（book_id=%d）' % (best['title'] or '未知书名', best['book_id']))
                return best
        finally:
            con.close()
        raise RuntimeError('DCStorage 中没有阅读记录：请先在好策 App 打开任意一本书的阅读页，再点“读取当前书籍”')
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        subprocess.run([adb, '-s', serial, 'shell', 'rm', remote], capture_output=True, timeout=30,
                       creationflags=runtime.NO_WINDOW)


def activate(book_id, novel_id=None, progress=print):
    bid = int(book_id)
    m = meta(bid)
    nid = _int(novel_id)
    if nid <= 0:
        # 没读到 novel_id 时不要覆盖已有值，否则阅读器接口取文会失效
        cfg = api.load_cfg()
        if _int(cfg.get('book_id')) == bid:
            nid = _int(cfg.get('novel_id'))
        if nid <= 0:
            nid = _int(m.get('novel_id'))
    api.set_active(bid, nid)
    if nid > 0:
        update_meta(bid, novel_id=nid)
    progress('已切换书籍：%s（%s）' % (m.get('short_title') or m.get('title'), bid))
    return m


def _migrate_legacy():
    bid = 31907
    target = paragraphs_path(bid)
    if not os.path.exists(target):
        for base in (runtime.BUNDLE, runtime.APP):
            src_p = os.path.join(base, 'data', 'paragraphs.json')
            if not os.path.exists(src_p):
                continue
            try:
                os.makedirs(book_dir(bid), exist_ok=True)
                shutil.copy2(src_p, target)
                src_t = os.path.join(base, 'data', 'book.txt')
                if os.path.exists(src_t) and not os.path.exists(txt_path(bid)):
                    shutil.copy2(src_t, txt_path(bid))
            except Exception:
                continue
            break
    if os.path.exists(target):
        m = read_json(meta_path(bid), {}) or {'book_id': bid}
        if not m.get('language'):
            ps = read_json(target, []) or []
            if ps:
                m['language'] = detect_language(' '.join(ps[:30]))
                m.setdefault('paragraph_count', len(ps))
                m.setdefault('legacy', True)
                m.setdefault('stub', not bool(m.get('title')))
                write_json(meta_path(bid), m)
    legacy_state = os.path.join(runtime.APP, 'run_state.json')
    if os.path.exists(legacy_state) and not os.path.exists(os.path.join(work_dir(bid), 'state.json')):
        try:
            os.makedirs(work_dir(bid), exist_ok=True)
            shutil.copy2(legacy_state, os.path.join(work_dir(bid), 'state.json'))
        except Exception:
            pass


_migrate_legacy()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'current'
    if cmd == 'current':
        print(json.dumps(current_book(), ensure_ascii=False))
    elif cmd == 'build':
        print(json.dumps(ensure_library(int(sys.argv[2]) if len(sys.argv) > 2 else None), ensure_ascii=False))
    elif cmd == 'status':
        print(json.dumps(status(int(sys.argv[2]) if len(sys.argv) > 2 else None), ensure_ascii=False))
    elif cmd == 'import':
        print(json.dumps(import_file(sys.argv[2]), ensure_ascii=False))
