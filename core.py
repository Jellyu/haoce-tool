import os, sys, json, re, time, random, hashlib, subprocess, asyncio, sqlite3, shutil, threading, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import runtime
import haoce_api as api
import books
import content
import tts
import paras as para_lib
from textutil import word_count, detect_language, cjk_count

APP_DIR = runtime.APP
BUNDLE_DIR = runtime.BUNDLE
DATA = os.path.join(APP_DIR, 'data')
BUNDLE_DATA = os.path.join(BUNDLE_DIR, 'data')
VOICES = {
    'en': ['en-US-AriaNeural', 'en-US-JennyNeural', 'en-US-AriaNeural', 'en-US-GuyNeural'],
    'zh': ['zh-CN-XiaoxiaoNeural', 'zh-CN-YunxiNeural', 'zh-CN-XiaoyiNeural', 'zh-CN-YunjianNeural'],
}
STOP = threading.Event()

RATE_LIMIT = 113


def log(msg):
    print(time.strftime('[%H:%M:%S]'), msg, flush=True)


def load_state(book_id=None):
    bid = int(book_id or api.active_book_id())
    path = os.path.join(books.work_dir(bid), 'state.json')
    if os.path.exists(path):
        return json.load(open(path, encoding='utf-8'))
    return {'langdu': [], 'zhaichao': [], 'taolun': {'posts': [], 'replies': []}}


def save_state(s, book_id=None):
    bid = int(book_id or api.active_book_id())
    path = os.path.join(books.work_dir(bid), 'state.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    json.dump(s, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def load_paragraphs(book_id=None):
    return books.paragraphs(book_id)


def wc(s):
    return word_count(s)


def clean(p, lang='en'):
    if lang == 'zh':
        if not 1 <= len(re.findall(r'[。！？!?]', p)) <= 50:
            return False
        cjk = cjk_count(p)
        return cjk >= 20 and cjk / max(1, len(p)) >= 0.5
    if not (2 <= len(re.findall(r'[.!?]', p)) <= 40):
        return False
    letters = sum(c.isalpha() or c.isspace() for c in p)
    if letters / max(1, len(p)) < 0.93:
        return False
    if p.isupper() or p.count('.') > 60:
        return False
    return True


def _range(minw, kind, lang):
    if minw <= 0:
        minw = 30 if lang == 'en' else 60
    if kind == 'langdu':
        lo = max(minw + 5, 30 if lang == 'en' else 80)
        hi = max(lo + 60, int(minw * 1.9))
    else:
        lo = max(minw + 5, 25 if lang == 'en' else 50)
        hi = max(lo + 70, int(minw * 3))
    return lo, hi


def fit_paragraph(p, lo, hi, lang):
    units = para_lib.split_sentences_zh(p) if lang == 'zh' else para_lib.split_sentences_en(p)
    if not units:
        return None
    weights = [wc(s) for s in units]
    sep = '' if lang == 'zh' else ' '
    windows = []
    for start in range(len(units)):
        total, parts = 0, []
        for s, n in zip(units[start:], weights[start:]):
            if total + n > hi:
                break
            parts.append(s)
            total += n
            if total >= lo:
                windows.append((start, len(parts), sep.join(parts)))
    if not windows:
        total, parts = 0, []
        for s, n in zip(units, weights):
            if total + n > hi:
                break
            parts.append(s)
            total += n
        if total >= lo:
            return sep.join(parts)
        return None
    return random.choice(windows)[2]


def _hash(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:12]


def candidates(minw, kind, used, book_id, need=1):
    m = books.cached_meta(book_id)
    ps = books.paragraphs(book_id)
    lang = m.get('language') or detect_language(' '.join(ps[:20]))
    lo, hi = _range(minw, kind, lang)
    primary, secondary, trimmed = [], [], []
    for p in ps:
        src = _hash(p)
        if src in used:
            continue
        n = wc(p)
        if n < minw or n > 1200:
            continue
        if lo <= n <= hi and clean(p, lang):
            primary.append((src, p, n, src))
        elif n < lo and clean(p, lang):
            secondary.append((src, p, n, src))
        elif n > hi:
            piece = fit_paragraph(p, lo, hi, lang)
            if piece and clean(piece, lang):
                trimmed.append((_hash(piece), piece, wc(piece), src))
    random.shuffle(primary)
    random.shuffle(secondary)
    random.shuffle(trimmed)
    return primary + secondary + trimmed


def ffmpeg():
    cfg = api.load_cfg()
    path = runtime.find_ffmpeg(cfg)
    if path:
        return path
    return shutil.which('ffmpeg')


def _audio_dir(book_id=None):
    try:
        bid = int(book_id or api.active_book_id())
        return os.path.join(books.work_dir(bid), 'audio')
    except Exception:
        return os.path.join(APP_DIR, 'audio')


def make_amr(text, tag, book_id=None, lang=None):
    lang = lang or detect_language(text)
    adir = _audio_dir(book_id)
    os.makedirs(adir, exist_ok=True)
    mp3 = os.path.join(adir, f'{tag}.mp3')
    amr = os.path.join(adir, f'{tag}.amr')
    ok = False
    voices = VOICES.get(lang, VOICES['en'])
    for attempt in range(4):
        voice = voices[(attempt + random.randint(0, 3)) % len(voices)]
        ok = asyncio.run(tts.synth(text, mp3, voice))
        if ok:
            break
    if not ok:
        raise RuntimeError('TTS 失败（网络或文本问题）')
    ff = ffmpeg()
    if not ff:
        raise RuntimeError('找不到 ffmpeg，可在 config.json 里配置 ffmpeg 路径')
    r = subprocess.run([ff, '-hide_banner', '-loglevel', 'error', '-y', '-i', mp3,
                        '-ar', '8000', '-ac', '1', '-c:a', 'libopencore_amrnb', '-b:a', '12.2k', amr],
                       capture_output=True, creationflags=runtime.NO_WINDOW)
    if r.returncode != 0 or not os.path.exists(amr):
        raise RuntimeError('AMR 转码失败: ' + r.stderr.decode('utf-8', 'replace')[:200])
    return amr


def retry_call(fn, logf=log, tries=3):
    for i in range(tries):
        r = fn()
        if isinstance(r, dict) and r.get('error') == 0:
            return r
        err = r.get('error') if isinstance(r, dict) else '?'
        if err == RATE_LIMIT:
            logf('触发频率限制，等待 20 秒…')
            time.sleep(20)
            continue
        return r
    return r


def _adb_bytes(adb, serial, args, timeout=60):
    return subprocess.run([adb, '-s', serial] + list(args), capture_output=True, timeout=timeout,
                          creationflags=runtime.NO_WINDOW)


def _pick_online(adb, serial):
    try:
        devices = runtime.online_devices(adb)
    except Exception:
        devices = []
    if serial in devices:
        return serial
    if devices:
        return devices[0]
    return None


def _wait_online(adb, serial, timeout=60):
    online = _pick_online(adb, serial)
    if online:
        return online
    # 没有在线设备：先尝试 connect 常见模拟器端口，再等待其上线
    online = runtime.ensure_online(adb, {'serial': serial})
    if online:
        return online
    try:
        subprocess.run([adb, 'wait-for-device'], capture_output=True, timeout=timeout,
                       creationflags=runtime.NO_WINDOW)
    except Exception:
        pass
    online = _pick_online(adb, serial)
    if online:
        return online
    raise RuntimeError('未发现在线设备，请确认 MuMu 已启动并已连接 adb')


def login_from_device(adb=None, serial=None):
    cfg = api.load_cfg()
    adb = adb or runtime.find_adb(cfg)
    if not adb:
        raise RuntimeError('找不到 adb：可放入 bin/adb.exe 或在 config.json 配置 adb 路径')
    serial = serial or runtime.pick_serial(adb, cfg)
    if not serial:
        raise RuntimeError('未发现在线设备，请确认 MuMu 已启动并已连接 adb')
    tmp = os.path.join(tempfile.gettempdir(), 'haoce_cookies_%d.db' % os.getpid())
    try:
        _adb_bytes(adb, serial, ['root'], timeout=40)
    except Exception:
        pass
    # adb root 会重启 adbd，期间设备短暂 offline，必须等它重新上线
    serial = _wait_online(adb, serial)
    try:
        if os.path.exists(tmp):
            os.remove(tmp)
    except Exception:
        pass
    # 直接读取字节再落盘：adb pull 无法在非 ASCII 路径下创建文件，
    # 而 exec-out 走 stdout，由 Python 写文件可绕开该限制
    got = _adb_bytes(adb, serial, ['exec-out', 'cat',
                                   '/data/data/app.haoce.com/app_webview/Default/Cookies'], 60)
    if got.returncode != 0 or len(got.stdout) < 1000:
        msg = got.stderr.decode('utf-8', 'replace').strip()
        raise RuntimeError('读取设备 Cookies 失败：' + (msg[:200] or '设备无响应'))
    with open(tmp, 'wb') as f:
        f.write(got.stdout)
    con = sqlite3.connect(tmp)
    row = con.execute("select value from cookies where host_key='appclient.haoce.com' and name='_UHAO'").fetchone()
    con.close()
    try:
        os.remove(tmp)
    except Exception:
        pass
    if not row:
        raise RuntimeError('设备中没有 _UHAO，请先在好策 App 内登录')
    new_cookie = '_UHAO=' + row[0]
    old_cookie = cfg.get('cookie') or ''
    old_uid, new_uid = api.uid_of(old_cookie), api.uid_of(new_cookie)
    switched = bool(old_uid and new_uid and old_uid != new_uid)
    cfg.update({'cookie': new_cookie, 'adb': adb, 'serial': serial})
    if switched:
        # 换号后旧书的 book_id / targets 缓存都属于上一个账号，必须作废
        old_bid = int(cfg.get('book_id') or 0)
        cfg['book_id'] = 0
        cfg['novel_id'] = 0
        if old_bid > 0:
            try:
                books.update_meta(old_bid, stub=True)
            except Exception:
                pass
    api.save_cfg(cfg)
    if switched:
        return ('账号已变更：%s → %s，已清除书籍选择'
                % (api.who_label(old_cookie) or '旧账号', api.who_label(new_cookie) or '新账号'))
    return '登录态已保存（%s）' % (api.who_label(new_cookie) or '未知账号')


def status(book_id=None):
    bid = int(book_id or api.active_book_id())
    c = api.counts(bid)
    m = books.cached_meta(bid)
    return {'book_id': bid, 'title': m.get('title', ''), 'counts': c,
            'targets': m.get('targets', {}), 'language': m.get('language', ''),
            'joined': c.get('joined')}


def _guard(c, logf):
    if not c.get('joined'):
        logf('当前书籍未加入阅读任务（bookJoin 为空），已跳过，避免无效提交')
        return False
    return True


def _used_hashes(st, key):
    used = set()
    for x in st.get(key, []):
        for k in ('hash', 'src'):
            if x.get(k):
                used.add(x[k])
    return used


def _book_lang(bid, m=None):
    m = m or books.cached_meta(bid)
    lang = m.get('language')
    if lang in ('en', 'zh'):
        return lang
    return detect_language(' '.join(books.paragraphs(bid)[:20]))


def run_langdu(target=None, logf=log, book_id=None):
    bid = int(book_id or api.active_book_id())
    m = books.meta(bid)
    target = int(target if target is not None else (m.get('targets') or {}).get('langdu') or 0)
    if target <= 0:
        logf('这本书没有朗读任务，已跳过')
        return 0
    c = api.counts(bid)
    if not _guard(c, logf):
        return 0
    have = c['langdu']
    need = max(0, target - have)
    if need == 0:
        logf(f'朗读已达标（{have}/{target}）')
        return 0
    st = load_state(bid)
    used = _used_hashes(st, 'langdu')
    minw = int((m.get('min_words') or {}).get('langdu') or 0)
    lang = _book_lang(bid, m)
    cands = candidates(minw, 'langdu', used, bid, need)
    logf(f'朗读：服务器已有 {have}，本次目标 {need}，候选段落 {len(cands)}，最短 {minw or "默认"} 词')
    ok = 0
    for h, p, nw, src in cands:
        if STOP.is_set():
            logf('已停止')
            break
        if ok >= need:
            break
        tag = 'ld_' + h
        try:
            amr = make_amr(p, tag, bid, lang)
            r = retry_call(lambda t=p, a=amr: api.upload_langdu(t, a, bid), logf)
            if r.get('error') == 0:
                ok += 1
                st['langdu'].append({'hash': h, 'src': src, 'words': nw, 'ts': int(time.time()),
                                     'topic_id': (r.get('redirect') or {}).get('url', '')})
                save_state(st, bid)
                logf(f'朗读 {have + ok}/{target} 成功（{nw} 词）')
            else:
                logf('朗读失败：' + str(r.get('error_des') or r.get('error')))
        except Exception as e:
            logf('朗读异常：' + type(e).__name__ + ' ' + str(e)[:160])
        time.sleep(random.uniform(2.0, 3.5))
    logf(f'朗读本轮完成 {ok}')
    return ok


def run_zhaichao(target=None, logf=log, book_id=None):
    bid = int(book_id or api.active_book_id())
    m = books.meta(bid)
    target = int(target if target is not None else (m.get('targets') or {}).get('zhaichao') or 0)
    if target <= 0:
        logf('这本书没有摘抄任务，已跳过')
        return 0
    c = api.counts(bid)
    if not _guard(c, logf):
        return 0
    have = c['zhaichao']
    need = max(0, target - have)
    if need == 0:
        logf(f'摘抄已达标（{have}/{target}）')
        return 0
    st = load_state(bid)
    used = _used_hashes(st, 'zhaichao')
    minw = int((m.get('min_words') or {}).get('zhaichao') or 0)
    lang = _book_lang(bid, m)
    cands = candidates(minw, 'zhaichao', used, bid, need)
    logf(f'摘抄：服务器已有 {have}，本次目标 {need}，候选段落 {len(cands)}，最短 {minw or "默认"} 词')
    ctx = content.build_context(m, books.paragraphs(bid))
    ok = 0
    used_t = set()
    for h, p, nw, src in cands:
        if STOP.is_set():
            logf('已停止')
            break
        if ok >= need:
            break
        insight = content.make_insight(p, used_t, ctx)
        try:
            r = retry_call(lambda e=p, i=insight: api.topic_add(6, i, excerpt=e, book_id=bid), logf)
            if r.get('error') == 0:
                ok += 1
                st['zhaichao'].append({'hash': h, 'src': src, 'words': nw,
                                       'insight_words': wc(insight), 'ts': int(time.time()),
                                       'topic_id': (r.get('redirect') or {}).get('url', '')})
                save_state(st, bid)
                logf(f'摘抄 {have + ok}/{target} 成功（原文 {nw} 词 / 见解 {wc(insight)} 词）')
            else:
                logf('摘抄失败：' + str(r.get('error_des') or r.get('error')))
        except Exception as e:
            logf('摘抄异常：' + type(e).__name__ + ' ' + str(e)[:160])
        time.sleep(random.uniform(2.5, 4.0))
    logf(f'摘抄本轮完成 {ok}')
    return ok


def run_taolun(posts=None, replies=None, logf=log, book_id=None):
    bid = int(book_id or api.active_book_id())
    m = books.meta(bid)
    tg = m.get('targets') or {}
    posts = int(posts if posts is not None else tg.get('topic') or 0)
    replies = int(replies if replies is not None else tg.get('reply') or 0)
    if posts <= 0 and replies <= 0:
        logf('这本书没有讨论任务，已跳过')
        return
    c = api.counts(bid)
    if not _guard(c, logf):
        return
    st = load_state(bid)
    ctx = content.build_context(m, books.paragraphs(bid))
    need_posts = max(0, posts - c['topic'])
    need_replies = max(0, replies - c['reply'])
    titles_done = {x['title'] for x in st['taolun']['posts']}
    if need_posts:
        for title, body in content.make_posts(ctx, need_posts, titles_done):
            if need_posts <= 0 or STOP.is_set():
                break
            r = retry_call(lambda t=title, b=body: api.topic_add(0, b, title=t, book_id=bid), logf)
            if r.get('error') == 0:
                st['taolun']['posts'].append({'title': title, 'ts': int(time.time()),
                                              'topic_id': (r.get('redirect') or {}).get('url', '')})
                save_state(st, bid)
                need_posts -= 1
                logf('发帖成功：' + title)
            else:
                logf('发帖失败：' + str(r.get('error_des') or r.get('error')))
            time.sleep(4)
    if need_replies and not STOP.is_set():
        me = api.uid()
        replied = {x['topic_id'] for x in st['taolun']['replies']}
        pool, seen = [], set()
        for page in range(1, 7):
            lst, pages, total = api.topic_list(0, page, bid)
            for x in lst:
                if (me and str(x.get('user_id')) == me) or x['topic_id'] in replied or x['topic_id'] in seen:
                    continue
                seen.add(x['topic_id'])
                pool.append(x)
            if page >= pages:
                break
            time.sleep(1.5)
        logf(f'讨论：待回复 {need_replies}，候选帖子 {len(pool)}')
        used_titles = set()
        ok = 0
        for x in pool:
            if STOP.is_set() or ok >= need_replies:
                break
            title = (x.get('topic') or 'this chapter').strip()
            if title in used_titles:
                continue
            used_titles.add(title)
            text = content.make_reply(title, ok, ctx)
            r = retry_call(lambda t=x['topic_id'], tx=text: api.comment_add(t, tx, book_id=bid), logf)
            if r.get('error') == 0:
                ok += 1
                st['taolun']['replies'].append({'topic_id': x['topic_id'], 'title': title,
                                                'words': wc(text), 'ts': int(time.time())})
                save_state(st, bid)
                logf(f'回复 {c["reply"] + ok}/{replies} 成功（{wc(text)} 词）')
            else:
                logf('回复失败：' + str(r.get('error_des') or r.get('error')))
            time.sleep(random.uniform(3.5, 5.0))
    logf('讨论任务结束')


def run_all(logf=log, book_id=None):
    bid = int(book_id or api.active_book_id())
    m = books.meta(bid)
    tg = m.get('targets') or {}
    logf('当前书籍：%s（%s）' % (m.get('short_title') or m.get('title'), bid))
    logf('任务目标：讨论 %d 帖/%d 回复，朗读 %d，摘抄 %d' %
         (tg.get('topic', 0), tg.get('reply', 0), tg.get('langdu', 0), tg.get('zhaichao', 0)))
    c = api.counts(bid)
    if not _guard(c, logf):
        return
    logf('当前：讨论 %d 帖/%d 回复，朗读 %d，摘抄 %d' % (c['topic'], c['reply'], c['langdu'], c['zhaichao']))
    run_langdu(None, logf, bid)
    run_zhaichao(None, logf, bid)
    run_taolun(None, None, logf, bid)
    s = status(bid)
    logf('完成：' + json.dumps(s['counts'], ensure_ascii=False))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
    args = [int(x) for x in sys.argv[2:] if x.isdigit()]
    if cmd == 'login':
        log(login_from_device())
    elif cmd == 'status':
        print(json.dumps(status(), ensure_ascii=False))
    elif cmd == 'langdu':
        run_langdu(*(args or [None]))
    elif cmd == 'zhaichao':
        run_zhaichao(*(args or [None]))
    elif cmd == 'taolun':
        run_taolun(*(args or [None, None]))
    elif cmd == 'all':
        run_all()
