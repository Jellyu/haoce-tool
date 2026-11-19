import os, re, sys, time, random, threading, subprocess, tempfile, html

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import runtime
import haoce_api as api


class PageTurner:
    SPEEDS = {'slow': (20, 30), 'normal': (14, 22), 'fast': (8, 14)}

    def __init__(self, log=print, on_status=None):
        self.log = log
        self.on_status = on_status or (lambda text: None)
        self.stop = threading.Event()
        cfg = api.load_cfg()
        self.adb = runtime.find_adb(cfg)
        if not self.adb:
            raise RuntimeError('找不到 adb：把 adb.exe 放进 bin/，或在 config.json 里配置 adb 路径')
        self.serial = runtime.pick_serial(self.adb, cfg)
        if not self.serial:
            raise RuntimeError('未发现已连接的模拟器，请先启动 MuMu')
        self.xml = os.path.join(tempfile.gettempdir(), f'haoce_ui_{os.getpid()}.xml')
        self.last_xml = ''
        self.W, self.H = self.screen_size()

    def _adb(self, *args, timeout=40):
        return subprocess.run([self.adb, '-s', self.serial] + [str(a) for a in args],
                              capture_output=True, text=True, encoding='utf-8',
                              errors='replace', timeout=timeout,
                              creationflags=runtime.NO_WINDOW)

    def screen_size(self):
        try:
            out = self._adb('shell', 'wm', 'size').stdout
            sizes = re.findall(r'(\d+)x(\d+)', out)
            if sizes:
                return int(sizes[-1][0]), int(sizes[-1][1])
        except Exception:
            pass
        return 900, 1600

    def dump_xml(self):
        last = ''
        for _ in range(3):
            r = self._adb('shell', 'uiautomator', 'dump', '/sdcard/haoce_ui.xml')
            last = (r.stdout or '') + (r.stderr or '')
            if 'dumped' in last.lower():
                p = self._adb('pull', '/sdcard/haoce_ui.xml', self.xml)
                if p.returncode == 0 and os.path.exists(self.xml) and os.path.getsize(self.xml) > 1000:
                    return open(self.xml, encoding='utf-8', errors='replace').read()
            time.sleep(1.2)
        raise RuntimeError('读取界面失败：' + last.strip()[:160])

    def read_page(self):
        try:
            xml = self.dump_xml()
        except Exception:
            return None
        self.last_xml = xml
        m = re.search(r'(?:text|content-desc)="(\d+)\s*/\s*(\d+)"', xml)
        if not m:
            return None
        ch = re.search(r'text="(Chapter [^"]{0,80})"', xml)
        return {'cur': int(m.group(1)), 'total': int(m.group(2)),
                'chapter': html.unescape(ch.group(1)) if ch else ''}

    def stable_page(self, n=2):
        last = None
        for i in range(n):
            p = self.read_page()
            if p:
                last = p
            if i < n - 1:
                time.sleep(0.8)
        return last

    def dismiss_anr(self):
        xml = self.last_xml or ''
        if '没有响应' not in xml:
            return False
        m = re.search(r'text="等待"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml)
        if not m:
            return False
        x = (int(m.group(1)) + int(m.group(3))) // 2
        y = (int(m.group(2)) + int(m.group(4))) // 2
        self._adb('shell', 'input', 'tap', x, y)
        self.log('检测到“好策没有响应”弹窗，已点“等待”继续')
        self._sleep(2)
        return True

    def swipe_next(self):
        y = int(self.H * 0.5 + random.randint(-30, 30))
        x1, x2 = int(self.W * 0.9), int(self.W * 0.1)
        dur = random.randint(420, 700)
        self._adb('shell', 'input', 'swipe', x1, y, x2, y, dur)

    def app_cpu(self):
        r = self._adb('shell', 'top', '-b', '-n', '1')
        for line in (r.stdout or '').splitlines():
            t = line.split()
            if len(t) >= 12 and t[-1] == 'app.haoce.com':
                try:
                    return float(t[8])
                except ValueError:
                    return None
        return None

    def wait_app_idle(self, cap=45):
        end = time.time() + cap
        quiet = 0
        warned = False
        while time.time() < end and not self.stop.is_set():
            cpu = self.app_cpu()
            if cpu is not None and cpu < 10:
                quiet += 1
                if quiet >= 2:
                    return True
            else:
                if not warned and cpu is not None:
                    self.log('App 主线程仍在渲染，等它空闲再滑…')
                    warned = True
                quiet = 0
            self._sleep(1.5)
        return False

    def swipe_chapter(self):
        y = int(self.H * 0.5)
        self._adb('shell', 'input', 'swipe', int(self.W * 0.8), y, int(self.W * 0.2), y,
                  random.randint(500, 800))

    def wait_forward(self, before, timeout=60):
        end = time.time() + timeout
        while time.time() < end and not self.stop.is_set():
            time.sleep(1.5)
            cpu = self.app_cpu()
            if cpu is not None and cpu >= 10:
                continue
            p = self.read_page()
            if p and p['cur'] > before['cur']:
                time.sleep(1.0)
                confirm = self.read_page()
                if confirm and confirm['cur'] == p['cur']:
                    return confirm
            if self.dismiss_anr():
                return None
        return None

    def turn_once(self, before):
        for attempt in range(1, 4):
            if self.stop.is_set():
                return None
            self.wait_app_idle()
            self.swipe_next()
            p = self.wait_forward(before)
            if p:
                self.log(f'翻页生效：{before["cur"]} -> {p["cur"]}/{p["total"]}'
                         + (f'（第 {attempt} 次滑动）' if attempt > 1 else ''))
                return p
            if self.stop.is_set():
                return None
            self.log(f'第 {attempt} 次滑动后 60 秒页码未变化')
        return None

    def _sleep(self, seconds):
        end = time.time() + seconds
        while time.time() < end and not self.stop.is_set():
            time.sleep(0.2)

    def _reading_pause(self, speed_name):
        lo, hi = self.SPEEDS.get(speed_name, self.SPEEDS['normal'])
        base = random.randint(lo, hi)
        wait = max(3, base + base * random.uniform(-0.2, 0.2))
        if random.random() < 0.15:
            wait += random.randint(3, 8)
        wait = int(wait)
        self.log(f'阅读等待 {wait} 秒…')
        end = time.time() + wait
        while time.time() < end and not self.stop.is_set():
            self.on_status(f'阅读中，下一次翻页 {max(0, int(end - time.time()))} 秒')
            time.sleep(0.5)

    def run(self, speed_name='normal', max_turns=None):
        self.stop.clear()
        self.wait_app_idle()
        p = self.stable_page(3)
        if not p and self.dismiss_anr():
            p = self.stable_page(2)
        if not p:
            self.log('未检测到阅读页码：请先在好策 App 里打开阅读页，再启动自动翻页')
            return
        chapter = p['chapter']
        self.log(f'已定位阅读页：{chapter or "未知章节"} 第 {p["cur"]}/{p["total"]} 页')
        bottom = 0
        turns = 0
        while not self.stop.is_set():
            self.wait_app_idle()
            p = self.stable_page(1)
            if not p:
                if self.dismiss_anr():
                    continue
                self.log('页码节点消失，停止自动翻页（请确认 App 仍在前台阅读页）')
                break
            if p['chapter']:
                chapter = p['chapter']
            self.on_status(f'{chapter or "阅读中"} {p["cur"]}/{p["total"]}'
                           + (f'  已翻 {turns} 页' if turns else ''))
            if p['cur'] >= p['total']:
                bottom += 1
                self.log(f'到达本章末页（{bottom}/3）：{p["cur"]}/{p["total"]}')
                if bottom >= 3:
                    self.log('切换下一章…')
                    self.wait_app_idle()
                    self.swipe_chapter()
                    self._sleep(4)
                    np = self.stable_page()
                    if np:
                        chapter = np['chapter'] or chapter
                        self.log(f'已切换章节：{chapter} 第 {np["cur"]}/{np["total"]} 页')
                    bottom = 0
                    self._sleep(2)
                    continue
            else:
                bottom = 0
                newp = self.turn_once(p)
                if not newp:
                    if self.stop.is_set():
                        break
                    self.log('本轮翻页未生效，稍后重试')
                    self._sleep(2)
                    continue
                turns += 1
                self.on_status(f'{chapter or "阅读中"} {newp["cur"]}/{newp["total"]}  已翻 {turns} 页')
            if max_turns is not None and turns >= max_turns:
                self.log(f'已翻 {turns} 页，按单次模式停止')
                break
            self._reading_pause(speed_name)
        self.log('自动翻页已停止')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    t = PageTurner(print, lambda s: print('[状态]', s, flush=True))
    if '--probe' in sys.argv:
        print(t.stable_page(3))
    else:
        speed = next((a for a in sys.argv[1:] if a in PageTurner.SPEEDS), 'normal')
        once = '--once' in sys.argv
        try:
            t.run(speed, max_turns=1 if once else None)
        except KeyboardInterrupt:
            t.stop.set()
