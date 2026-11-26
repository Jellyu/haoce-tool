import os, sys, json, shutil, subprocess

FROZEN = bool(getattr(sys, 'frozen', False))
APP = os.path.dirname(os.path.abspath(sys.executable)) if FROZEN else os.path.dirname(os.path.abspath(__file__))
BUNDLE = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(APP, 'config.json')
DEFAULT_CONFIG = os.path.join(BUNDLE, 'config.default.json')
BIN_DIRS = [os.path.join(APP, 'bin'), os.path.join(BUNDLE, 'bin')]
MUMU_ADB = r'H:\MuMuPlayer\nx_device\15.0\shell\adb.exe'
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def ensure_stdio():
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w', encoding='utf-8')


ensure_stdio()


def find_bin(name):
    for d in BIN_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def default_config():
    if os.path.exists(DEFAULT_CONFIG):
        return json.load(open(DEFAULT_CONFIG, encoding='utf-8'))
    return {'cookie': '', 'adb': '', 'serial': '127.0.0.1:16384', 'book_id': 0,
            'novel_id': 0, 'ffmpeg': '', 'pdftotext': ''}


def ensure_config():
    if not os.path.exists(CONFIG):
        json.dump(default_config(), open(CONFIG, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return CONFIG


def find_adb(cfg=None):
    cfg = cfg or {}
    for p in (cfg.get('adb'), find_bin('adb.exe'), MUMU_ADB):
        if p and os.path.exists(p):
            return p
    return shutil.which('adb')


def find_ffmpeg(cfg=None):
    cfg = cfg or {}
    for p in (cfg.get('ffmpeg'), find_bin('ffmpeg.exe')):
        if p and os.path.exists(p):
            return p
    return shutil.which('ffmpeg')


def find_pdftotext(cfg=None):
    cfg = cfg or {}
    for p in (cfg.get('pdftotext'), find_bin('pdftotext.exe')):
        if p and os.path.exists(p):
            return p
    return shutil.which('pdftotext')


def online_devices(adb):
    r = subprocess.run([adb, 'devices'], capture_output=True, text=True, timeout=20,
                       creationflags=NO_WINDOW)
    out = []
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == 'device':
            out.append(parts[0])
    return out


MUMU_ENDPOINTS = ('127.0.0.1:16384', '127.0.0.1:7555', '127.0.0.1:5555', '127.0.0.1:16416')


def _devices(adb):
    try:
        return online_devices(adb)
    except Exception:
        return []


def _connect(adb, endpoint, timeout=8):
    try:
        subprocess.run([adb, 'connect', endpoint], capture_output=True, timeout=timeout,
                       creationflags=NO_WINDOW)
    except Exception:
        pass


def ensure_online(adb, cfg=None):
    cfg = cfg or {}
    serial = (cfg.get('serial') or '').strip()
    devices = _devices(adb)
    if devices:
        return serial if serial in devices else devices[0]
    # MuMu 的 adb 端口默认不在 adb devices 里，必须先 connect 才会出现
    tried = set()
    for ep in ([serial] if serial else []) + list(MUMU_ENDPOINTS):
        if ep in tried:
            continue
        tried.add(ep)
        _connect(adb, ep)
        devices = _devices(adb)
        if devices:
            return serial if serial in devices else devices[0]
    return ''


def pick_serial(adb, cfg=None):
    # 没有在线设备时返回空串，让调用方给出明确提示，而不是拿一个死地址去 wait-for-device
    return ensure_online(adb, cfg)
