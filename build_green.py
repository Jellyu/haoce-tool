import os, sys, json, shutil, subprocess, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
NAME = 'haoce-tool'
STAGE = os.path.join(HERE, 'build_out')
BUILD = os.path.join(HERE, 'build')
APP_DIR = os.path.join(PARENT, NAME + '-green')
ZIP_PATH = os.path.join(PARENT, NAME + '-green.zip')
MUMU_ADB = r'H:\MuMuPlayer\nx_device\15.0\shell\adb.exe'
PDFTOTEXT_FILES = ('pdftotext.exe', 'libgcc_s_seh-1.dll', 'libstdc++-6.dll', 'libwinpthread-1.dll')


def load_cfg():
    p = os.path.join(HERE, 'config.json')
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding='utf-8'))
        except Exception:
            pass
    return {}


def pick(candidates, name):
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return shutil.which(name)


def run(cmd):
    print('>', ' '.join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=HERE)
    if r.returncode != 0:
        raise SystemExit('build failed, exit code %d' % r.returncode)


def copy_bins():
    cfg = load_cfg()
    adb = pick([cfg.get('adb'), os.environ.get('ADB_PATH'), MUMU_ADB], 'adb')
    ffmpeg = pick([cfg.get('ffmpeg'), os.environ.get('FFMPEG_PATH'),
                   os.path.join(HERE, 'bin', 'ffmpeg.exe')], 'ffmpeg')
    if not adb:
        raise SystemExit('adb not found; set ADB_PATH or config.json "adb"')
    if not ffmpeg:
        raise SystemExit('ffmpeg not found; put it in bin/ffmpeg.exe or set FFMPEG_PATH')

    dest = os.path.join(APP_DIR, 'bin')
    os.makedirs(dest, exist_ok=True)
    adb_dir = os.path.dirname(adb)
    for f in ('adb.exe', 'AdbWinApi.dll', 'AdbWinUsbApi.dll'):
        src = os.path.join(adb_dir, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dest, f))
    if not os.path.exists(os.path.join(dest, 'adb.exe')):
        raise SystemExit('missing adb.exe next to ' + adb)
    shutil.copy2(ffmpeg, os.path.join(dest, 'ffmpeg.exe'))
    for f in PDFTOTEXT_FILES:
        src = os.path.join(HERE, 'bin', f)
        if not os.path.exists(src):
            raise SystemExit('missing PDF text component: bin/' + f)
        shutil.copy2(src, os.path.join(dest, f))


def main():
    for d in (STAGE, BUILD, APP_DIR):
        if os.path.exists(d):
            shutil.rmtree(d)

    run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed', '--onedir',
         '--noupx', '--name', NAME, '--distpath', STAGE, '--workpath', BUILD,
         '--collect-all', 'edge_tts', '--hidden-import', 'pypdf', 'app.py'])

    shutil.move(os.path.join(STAGE, NAME), APP_DIR)
    shutil.rmtree(STAGE, ignore_errors=True)

    copy_bins()
    for folder in ('data', 'auto_turner'):
        src = os.path.join(HERE, folder)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(APP_DIR, folder))
    shutil.copy2(os.path.join(HERE, 'config.default.json'), os.path.join(APP_DIR, 'config.default.json'))
    internal = os.path.join(APP_DIR, '_internal')
    if os.path.isdir(internal):
        shutil.copy2(os.path.join(HERE, 'config.default.json'), os.path.join(internal, 'config.default.json'))
    shutil.copy2(os.path.join(HERE, 'README.md'), os.path.join(APP_DIR, 'README.md'))

    cfg = json.load(open(os.path.join(HERE, 'config.default.json'), encoding='utf-8'))
    json.dump(cfg, open(os.path.join(APP_DIR, 'config.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)
    with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, dirs, files in os.walk(APP_DIR):
            for f in files:
                p = os.path.join(root, f)
                z.write(p, os.path.relpath(p, PARENT))
    print('app dir :', APP_DIR)
    print('archive :', ZIP_PATH, '%.1f MB' % (os.path.getsize(ZIP_PATH) / 1048576))


if __name__ == '__main__':
    main()
