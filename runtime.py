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


def pick_serial(adb, cfg=None):
    cfg = cfg or {}
    serial = cfg.get('serial')
    try:
        devices = online_devices(adb)
    except Exception:
        devices = []
    if serial and (not devices or serial in devices):
        return serial
    if devices:
        return devices[0]
    return serial or '127.0.0.1:16384'
