import urllib.request, urllib.parse, json, time, os, sys, uuid, re
import runtime
import textutil

HOST = 'https://appclient.haoce.com'
UA = ('Mozilla/5.0 (Linux; Android 15; PGZ110 Build/AP3A.240905.015.A2; wv) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Version/4.0 Chrome/120.0.6099.230 Mobile Safari/537.36 uni-app Html5Plus/1.0 (Immersed/30.0)')

CFG_PATH = runtime.CONFIG


def load_cfg():
    runtime.ensure_config()
    return json.load(open(CFG_PATH, encoding='utf-8'))


def save_cfg(cfg):
    json.dump(cfg, open(CFG_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def active_book_id():
    cfg = load_cfg()
    try:
        bid = int(cfg.get('book_id') or 0)
    except Exception:
        bid = 0
    if bid <= 0:
        raise RuntimeError('尚未选择书籍：请先在 GUI 点“读取当前书籍”，或填写书籍 ID 后点“加载”')
    return bid


def set_active(book_id, novel_id=None):
    cfg = load_cfg()
    cfg['book_id'] = int(book_id)
    if novel_id is not None:
        cfg['novel_id'] = int(novel_id)
    save_cfg(cfg)
    return cfg['book_id']


def cookie():
    c = load_cfg().get('cookie')
    if not c:
        raise RuntimeError('缺少登录态：请先点“读取登录态”，或在设备上的好策 App 重新登录')
    return c


def uid():
    try:
        m = re.search(r'_UHAO=([^;]+)', cookie())
        if not m:
            return ''
        data = json.loads(urllib.parse.unquote(m.group(1)))
        return str((data or {}).get('uid') or '')
    except Exception:
        return ''


def request(path, data=None, timeout=40, retries=2):
    url = path if path.startswith('http') else HOST + path
    d = dict(data or {})
    d.setdefault('MB_time', str(int(time.time() * 1000)))
    d.setdefault('MB_version', '20240311')
    body = urllib.parse.urlencode(d).encode()
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=body, headers={
                'User-Agent': UA, 'Cookie': cookie(), 'Referer': HOST + '/app/page/bookOne',
                'X-Display': 'json', 'X-Requested-With': '',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})
            raw = urllib.request.urlopen(req, timeout=timeout).read()
            return json.loads(raw)
        except Exception as e:
            last = e
            time.sleep(2)
    raise RuntimeError(f'request failed {path}: {last}')


def multipart(path, fields, file_field, file_path, ctype='audio/amr', timeout=180):
    boundary = '----WebKitFormBoundary' + uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode('utf-8'))
    fn = os.path.basename(file_path)
    parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{fn}"\r\n'
                  f'Content-Type: {ctype}\r\n\r\n').encode('utf-8'))
    parts.append(open(file_path, 'rb').read())
    parts.append(f'\r\n--{boundary}--\r\n'.encode('utf-8'))
    body = b''.join(parts)
    req = urllib.request.Request(HOST + path, data=body, headers={
        'User-Agent': UA, 'Cookie': cookie(), 'Referer': HOST + '/app/page/topicNew?book_id=%d&tag_id=3' % active_book_id(),
        'X-Display': 'json', 'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Content-Length': str(len(body))})
    raw = urllib.request.urlopen(req, timeout=timeout).read()
    return json.loads(raw)


def book_detail(book_id=None):
    bid = int(book_id or active_book_id())
    r = request(f'/app/bookOne/detail/{bid}', {'book_id': str(bid)})
    return r.get('data') or {}


def counts(book_id=None):
    d = book_detail(book_id)
    j = d.get('bookJoin') or {}
    joined = any(j.get(k) is not None for k in ('topic_cnt', 'comment_cnt', 'tag_3_cnt', 'tag_5_cnt', 'tag_6_cnt'))
    return {'topic': int(j.get('topic_cnt') or 0), 'reply': int(j.get('comment_cnt') or 0),
            'langdu': int(j.get('tag_3_cnt') or 0), 'report': int(j.get('tag_5_cnt') or 0),
            'zhaichao': int(j.get('tag_6_cnt') or 0), 'joined': joined}


def topic_list(tag_id, page=1, book_id=None):
    bid = int(book_id or active_book_id())
    r = request(f'/app/bookOne/topicList/{bid}?pageno={page}', {'tag_id': str(tag_id)})
    d = (r.get('data') or {}).get('topic_list') or {}
    return d.get('list') or [], d.get('page_total') or 1, d.get('total_cnt')


def topic_add(tag_id, content, title='', excerpt=None, book_id=None, extra=None):
    bid = int(book_id or active_book_id())
    data = {'topic': title, 'topic_info': content, 'tag_id': str(tag_id), 'book_id': str(bid),
            'type': '0', 'word_cnt': str(textutil.word_count(content)),
            'topic_id': '0', 't_id': '0', 'attr': {'stop': 0}}
    if excerpt is not None:
        data['topic_info_yanwen'] = excerpt
        data['yuan_word_cnt'] = str(textutil.word_count(excerpt))
    if extra:
        data.update(extra)
    return request('/book/topicAdd', data)


def comment_add(topic_id, comment, reply_id=0, book_id=None):
    bid = int(book_id or active_book_id())
    data = {'topic_id': str(topic_id), 'comment': comment, 'reply_id': str(reply_id),
            'word_cnt': str(textutil.word_count(comment))}
    path = f'/book/commentAdd/{bid}/{topic_id}'
    if reply_id:
        path += f'/{reply_id}'
    return request(path, data)


def upload_langdu(text, amr_path, book_id=None, extra=None):
    bid = int(book_id or active_book_id())
    size = os.path.getsize(amr_path)
    dur = (size - 6) / 32 * 0.02
    words = str(textutil.word_count(text))
    fields = {'topic': '', 'topic_info': text, 'type': '0',
              'attr': {'path': '/storage/emulated/0/Android/data/app.haoce.com/apps/__UNI__ED95160/doc/audio/tts.amr',
                       'time': int(dur), 'ext': 'amr'},
              'tag_id': '3', 'book_id': str(bid), 'word_cnt': words,
              'topic_id': '0', 'yuan_word_cnt': words,
              'topic_info_yanwen': text, 'MB_time': str(int(time.time() * 1000))}
    if extra:
        fields.update(extra)
    return multipart('/book/topicAdd/tag3', fields, 'file', amr_path)
