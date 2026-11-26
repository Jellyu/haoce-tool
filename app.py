import os, sys, json, time, threading, queue, tkinter as tk
from tkinter import ttk, messagebox, filedialog

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import core
import turner
import books
import runtime
import haoce_api as api

BG = '#0b1220'
SURFACE = '#131c2e'
SURFACE2 = '#0f1729'
BORDER = '#243352'
FG = '#e8eef8'
MUTED = '#8fa3c0'
DIM = '#5b6b86'
ACC = '#38bdf8'
OK = '#34d399'
WARN = '#fbbf24'
ERR = '#f87171'

BUTTON_STYLES = {
    'primary': ('#2563eb', '#3b82f6', '#ffffff'),
    'ghost': ('#1c2942', '#26374f', '#dbe6f6'),
    'green': ('#0f7a5a', '#12956d', '#eafff7'),
    'red': ('#7f2231', '#9b2b3d', '#ffe9ec'),
    'cyan': ('#0e5c78', '#127a9e', '#e6f8ff'),
}

TASKS = (('topic', '讨论帖'), ('reply', '回复'), ('langdu', '朗读'),
         ('zhaichao', '摘抄'), ('report', '报告'))

STATE_COLORS = {'达标': OK, '进行中': ACC, '未加入': WARN, '异常': ERR, '未选书': DIM}


def mk_btn(parent, text, cmd, kind='ghost', font=('Microsoft YaHei UI', 10), padx=12, pady=6):
    bg, hov, fg = BUTTON_STYLES[kind]
    b = tk.Button(parent, text=text, command=cmd, font=font, bg=bg, fg=fg,
                  activebackground=hov, activeforeground=fg, relief='flat', bd=0,
                  highlightthickness=0, disabledforeground=DIM, cursor='hand2',
                  padx=padx, pady=pady)
    b._bg, b._hov, b._fg = bg, hov, fg

    def enter(_e):
        if str(b['state']) != 'disabled':
            b.configure(bg=b._hov)

    def leave(_e):
        if str(b['state']) != 'disabled':
            b.configure(bg=b._bg)

    b.bind('<Enter>', enter)
    b.bind('<Leave>', leave)
    return b


def set_enabled(b, on):
    if on:
        b.configure(state='normal', bg=b._bg, fg=b._fg, cursor='hand2')
    else:
        b.configure(state='disabled', bg=SURFACE2, fg=DIM, cursor='')


def card(parent):
    return tk.Frame(parent, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)


class Bar(tk.Canvas):
    def __init__(self, parent, height=5):
        super().__init__(parent, width=1, height=height, bg=SURFACE2,
                         highlightthickness=0, bd=0)
        self._h = height
        self._ratio, self._color = -1.0, None
        self._rect = self.create_rectangle(0, 0, 0, height, fill=ACC, width=0)
        self.bind('<Configure>', lambda e: self._redraw())

    def _redraw(self):
        w = max(self.winfo_width(), 1)
        self.coords(self._rect, 0, 0, w * max(self._ratio, 0.0), self._h)
        self.itemconfigure(self._rect, fill=self._color or ACC)

    def set(self, ratio, color=ACC):
        r = max(0.0, min(1.0, float(ratio)))
        if abs(r - self._ratio) < 0.002 and color == self._color:
            return
        self._ratio, self._color = r, color
        self._redraw()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('好策读书自动化助手')
        self.geometry('1140x800')
        self.minsize(1080, 720)
        self.configure(bg=BG)
        self.q = queue.Queue()
        self.busy = False
        self.turner = None
        self.targets = {}
        self.joined = None
        self.task_btns = {}
        self.run_btn = None
        self.buttons = []
        self.vars = {}
        self.prog = {}
        self.subs = {}
        self._last_state = None
        self.book_var = tk.StringVar(value='书籍：未选择（点“读取当前书籍”）')
        self.book_id_var = tk.StringVar(value='')
        self.page_var = tk.StringVar(value='页码：-（请先在 App 打开阅读页）')
        self.speed = tk.StringVar(value='normal')
        self._build()
        self._show_account()
        self._after_id = self.after(200, self._drain)
        self.protocol('WM_DELETE_WINDOW', self._close)
        self.refresh_async()

    # ---------- 界面 ----------
    def _build(self):
        self._build_header()
        body = tk.Frame(self, bg=BG)
        body.pack(fill='both', expand=True, padx=14, pady=(0, 12))
        self._build_book(body)
        self._build_stats(body)
        self._build_actions(body)
        self._build_turn(body)
        self._build_log(body)

    def _build_header(self):
        h = tk.Frame(self, bg=BG)
        h.pack(fill='x', padx=16, pady=(14, 8))
        left = tk.Frame(h, bg=BG)
        left.pack(side='left')
        tk.Label(left, text='好策读书自动化助手', font=('Microsoft YaHei UI', 18, 'bold'),
                 fg=FG, bg=BG).pack(anchor='w')
        tk.Label(left, text='朗读 TTS · 摘抄见解 · 讨论回复 · 自动翻页 · 任意书籍',
                 font=('Microsoft YaHei UI', 9), fg=DIM, bg=BG).pack(anchor='w', pady=(2, 0))
        self.pill = tk.Label(h, text=' 就绪 ', font=('Microsoft YaHei UI', 10, 'bold'),
                             fg='#062033', bg=ACC, padx=10, pady=4)
        self.pill.pack(side='right', pady=(6, 0))
        self.acct_var = tk.StringVar(value='账号：未登录')
        self.acct_lbl = tk.Label(h, textvariable=self.acct_var, font=('Microsoft YaHei UI', 10),
                                 fg=DIM, bg=BG)
        self.acct_lbl.pack(side='right', padx=(0, 12), pady=(6, 0))

    def _build_book(self, parent):
        c = card(parent)
        c.pack(fill='x', pady=(0, 8))
        tk.Label(c, text='当前书籍', font=('Microsoft YaHei UI', 9), fg=DIM,
                 bg=SURFACE).pack(side='left', padx=(14, 10), pady=12)
        tk.Label(c, textvariable=self.book_var, font=('Microsoft YaHei UI', 10, 'bold'),
                 fg=WARN, bg=SURFACE, anchor='w').pack(side='left', fill='x', expand=True, pady=12)
        right = tk.Frame(c, bg=SURFACE)
        right.pack(side='right', padx=10, pady=8)
        b = mk_btn(right, '读取当前书籍', self.read_current, 'primary',
                   font=('Microsoft YaHei UI', 9), padx=10, pady=4)
        b.pack(side='left', padx=3)
        self.buttons.append(b)
        for text, cmd in (('构建书籍库', self.build_library), ('导入文本', self.import_text)):
            b = mk_btn(right, text, cmd, 'ghost', font=('Microsoft YaHei UI', 9), padx=10, pady=4)
            b.pack(side='left', padx=3)
            self.buttons.append(b)
        tk.Entry(right, textvariable=self.book_id_var, width=8, font=('Consolas', 10),
                 bg=SURFACE2, fg=FG, insertbackground=ACC, relief='flat',
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACC).pack(side='left', padx=(8, 3), ipady=4)
        b = mk_btn(right, '加载 ID', self.load_id, 'ghost', font=('Microsoft YaHei UI', 9),
                   padx=10, pady=4)
        b.pack(side='left', padx=3)
        self.buttons.append(b)

    def _build_stats(self, parent):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill='x', pady=(0, 8))
        for i, (key, label) in enumerate(TASKS):
            row.columnconfigure(i, weight=1, uniform='stat')
            c = card(row)
            c.grid(row=0, column=i, sticky='nsew', padx=(0 if i == 0 else 8, 0))
            inner = tk.Frame(c, bg=SURFACE)
            inner.pack(fill='x', padx=12, pady=(9, 10))
            head = tk.Frame(inner, bg=SURFACE)
            head.pack(fill='x')
            tk.Label(head, text=label, font=('Microsoft YaHei UI', 9), fg=MUTED,
                     bg=SURFACE).pack(side='left')
            sub = tk.StringVar(value='-')
            self.subs[key] = sub
            tk.Label(head, textvariable=sub, font=('Microsoft YaHei UI', 8), fg=DIM,
                     bg=SURFACE).pack(side='right')
            v = tk.StringVar(value='-')
            self.vars[key] = v
            tk.Label(inner, textvariable=v, font=('Consolas', 20, 'bold'), fg=FG,
                     bg=SURFACE).pack(anchor='w', pady=(2, 6))
            bar = Bar(inner, height=5)
            bar.pack(fill='x')
            self.prog[key] = bar
        self.vars['state'] = tk.StringVar(value='-')

    def _build_actions(self, parent):
        c = card(parent)
        c.pack(fill='x', pady=(0, 8))
        row = tk.Frame(c, bg=SURFACE)
        row.pack(fill='x', padx=12, pady=10)
        tk.Label(row, text='任务', font=('Microsoft YaHei UI', 9), fg=DIM,
                 bg=SURFACE).pack(side='left', padx=(0, 10))
        self.run_btn = mk_btn(row, '一键完成', self.run_all, 'primary', padx=18, pady=7)
        self.run_btn.pack(side='left', padx=(0, 10))
        self.buttons.append(self.run_btn)
        for key, text, cmd, kind in (('langdu', '朗读', lambda: self.run_task('langdu'), 'ghost'),
                                     ('zhaichao', '摘抄', lambda: self.run_task('zhaichao'), 'ghost'),
                                     ('taolun', '讨论', lambda: self.run_task('taolun'), 'cyan')):
            b = mk_btn(row, text, cmd, kind, padx=14, pady=7)
            b.pack(side='left', padx=4)
            self.task_btns[key] = b
            self.buttons.append(b)
        self.stop_btn = mk_btn(row, '停止', self.stop, 'red', padx=16, pady=7)
        self.stop_btn.pack(side='right')
        set_enabled(self.stop_btn, False)
        b = mk_btn(row, '刷新状态', self.refresh_async, 'ghost', padx=12, pady=7)
        b.pack(side='right', padx=6)
        self.buttons.append(b)
        b = mk_btn(row, '读取登录态', self.login, 'ghost', padx=12, pady=7)
        b.pack(side='right', padx=6)
        self.buttons.append(b)
        self.clear_btn = mk_btn(row, '清除登录态', self.clear_login, 'red', padx=12, pady=7)
        self.clear_btn.pack(side='right', padx=6)
        self.buttons.append(self.clear_btn)

    def _build_turn(self, parent):
        c = card(parent)
        c.pack(fill='x', pady=(0, 8))
        row = tk.Frame(c, bg=SURFACE)
        row.pack(fill='x', padx=12, pady=10)
        tk.Label(row, text='自动翻页', font=('Microsoft YaHei UI', 10, 'bold'), fg=ACC,
                 bg=SURFACE).pack(side='left', padx=(0, 12))
        self.speed_btns = {}
        for val, label in (('slow', '慢速'), ('normal', '正常'), ('fast', '快速')):
            b = mk_btn(row, label, lambda v=val: self._set_speed(v), 'ghost',
                       font=('Microsoft YaHei UI', 9), padx=12, pady=5)
            b.pack(side='left', padx=2)
            self.speed_btns[val] = b
            self.buttons.append(b)
        self._set_speed('normal')
        self.turn_btn = mk_btn(row, '开始翻页', self.start_turn, 'green', padx=16, pady=5)
        self.turn_btn.pack(side='left', padx=(12, 6))
        self.buttons.append(self.turn_btn)
        tk.Label(row, textvariable=self.page_var, font=('Microsoft YaHei UI', 9), fg=WARN,
                 bg=SURFACE).pack(side='left', padx=10)

    def _build_log(self, parent):
        c = card(parent)
        c.pack(fill='both', expand=True)
        head = tk.Frame(c, bg=SURFACE)
        head.pack(fill='x', padx=12, pady=(9, 0))
        tk.Label(head, text='运行日志', font=('Microsoft YaHei UI', 9, 'bold'), fg=MUTED,
                 bg=SURFACE).pack(side='left')
        mk_btn(head, '清空', self._clear_log, 'ghost', font=('Microsoft YaHei UI', 8),
               padx=10, pady=2).pack(side='right')
        wrap = tk.Frame(c, bg=SURFACE)
        wrap.pack(fill='both', expand=True, padx=12, pady=(6, 12))
        self.logbox = tk.Text(wrap, bg='#070d1a', fg='#c7d4e8', insertbackground=ACC,
                              font=('Consolas', 10), relief='flat', wrap='word', bd=0,
                              padx=10, pady=8, highlightthickness=1,
                              highlightbackground=BORDER)
        sb = tk.Scrollbar(wrap, command=self.logbox.yview, bg=SURFACE, troughcolor=SURFACE2,
                          bd=0, width=10)
        self.logbox.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.logbox.pack(side='left', fill='both', expand=True)
        self.logbox.tag_configure('ts', foreground='#44556f')
        self.logbox.tag_configure('ok', foreground=OK)
        self.logbox.tag_configure('err', foreground=ERR)
        self.logbox.tag_configure('warn', foreground=WARN)
        self.logbox.tag_configure('info', foreground='#c7d4e8')
        self.logbox.configure(state='disabled')

    def _clear_log(self):
        self.logbox.configure(state='normal')
        self.logbox.delete('1.0', 'end')
        self.logbox.configure(state='disabled')

    def _close(self):
        try:
            self.after_cancel(self._after_id)
        except Exception:
            pass
        core.STOP.set()
        if self.turner:
            self.turner.stop.set()
        self.destroy()

    def log(self, msg):
        self.q.put(str(msg))

    def _append_log(self, text):
        tag = 'info'
        if any(k in text for k in ('失败', '异常', '错误', 'Error', 'Traceback')):
            tag = 'err'
        elif any(k in text for k in ('成功', '完成', '达标', '就绪', '已刷新')):
            tag = 'ok'
        elif any(k in text for k in ('请先', '未加入', '尚未', '跳过', '缺少')):
            tag = 'warn'
        self.logbox.configure(state='normal')
        self.logbox.insert('end', time.strftime('%H:%M:%S') + '  ', 'ts')
        self.logbox.insert('end', text + '\n', tag)
        self.logbox.see('end')
        self.logbox.configure(state='disabled')

    def _drain(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if isinstance(msg, tuple) and msg[0] == 'page':
                    self.page_var.set(msg[1])
                    continue
                if isinstance(msg, tuple) and msg[0] == 'book':
                    self._show_book(msg[1])
                    continue
                self._append_log(str(msg))
        except queue.Empty:
            pass
        self._sync_stats()
        self.after(200, self._drain)

    def _sync_stats(self):
        t = self.targets or {}
        for key, _ in TASKS:
            tgt = int(t.get(key) or 0)
            raw = self.vars[key].get() if key in self.vars else '-'
            try:
                have = int(raw)
            except (TypeError, ValueError):
                have = None
            sub, bar = self.subs.get(key), self.prog.get(key)
            if have is None:
                if sub:
                    sub.set('-')
                if bar:
                    bar.set(0, DIM)
                continue
            if tgt <= 0:
                if sub:
                    sub.set('无任务')
                if bar:
                    bar.set(0, DIM)
            elif have >= tgt:
                if sub:
                    sub.set('已达标')
                if bar:
                    bar.set(1.0, OK)
            else:
                if sub:
                    sub.set('%d/%d' % (have, tgt))
                if bar:
                    bar.set(have / tgt, ACC)
        st = self.vars['state'].get() if 'state' in self.vars else '-'
        if st != self._last_state:
            self._last_state = st
            color = STATE_COLORS.get(st, DIM)
            self.pill.configure(text=' %s ' % st, bg=color,
                                fg='#062033' if color != DIM else '#0b1220')

    def _show_book(self, info):
        bid = int(info.get('book_id') or 0)
        self.targets = info.get('targets') or {}
        self.joined = info.get('joined')
        if bid <= 0:
            self.book_var.set('书籍：未选择（点“读取当前书籍”）')
            self.book_id_var.set('')
            self._update_task_buttons()
            return
        self.book_id_var.set(str(bid))
        title = info.get('short_title') or info.get('title') or ('书籍 %d' % bid)
        if len(title) > 42:
            title = title[:41] + '…'
        bits = []
        if info.get('language'):
            bits.append(info['language'])
        if info.get('paragraphs'):
            bits.append('库 %d 段' % info['paragraphs'])
        if info.get('joined') is False:
            bits.append('未加入任务')
        suffix = (' · ' + ' · '.join(bits)) if bits else ''
        self.book_var.set('书籍：%s（ID %d）%s' % (title, bid, suffix))
        self._update_task_buttons()

    def _update_task_buttons(self):
        t = self.targets or {}
        labels = {'langdu': '朗读 %d' % int(t.get('langdu') or 0),
                  'zhaichao': '摘抄 %d' % int(t.get('zhaichao') or 0),
                  'taolun': '讨论 %d+%d' % (int(t.get('topic') or 0), int(t.get('reply') or 0))}
        for key, b in self.task_btns.items():
            b.configure(text=labels.get(key, b['text']))
            n = {'langdu': t.get('langdu'), 'zhaichao': t.get('zhaichao'),
                 'taolun': (t.get('topic') or 0) + (t.get('reply') or 0)}[key]
            set_enabled(b, (not self.busy) and self.joined is not False and bool(n))
        if self.run_btn:
            any_task = any(int(t.get(k) or 0) > 0 for k in ('langdu', 'zhaichao', 'topic', 'reply'))
            set_enabled(self.run_btn,
                        (not self.busy) and self.joined is not False and any_task)

    def set_busy(self, busy):
        self.busy = busy
        for b in self.buttons:
            set_enabled(b, not busy)
        if getattr(self, 'stop_btn', None):
            set_enabled(self.stop_btn, busy)
        if not busy:
            self._update_task_buttons()

    def _active_id(self, quiet=False):
        try:
            return api.active_book_id()
        except Exception as e:
            if not quiet:
                self.log(str(e))
            return 0

    def _push_book(self, bid):
        try:
            m = books.meta(bid)
            st = books.status(bid)
            self.q.put(('book', {'book_id': bid, 'title': m.get('title'),
                                 'short_title': m.get('short_title'), 'targets': m.get('targets'),
                                 'language': st.get('language') or m.get('language'),
                                 'paragraphs': st.get('paragraphs'), 'joined': st.get('joined')}))
        except Exception as e:
            self.log('读取书籍信息失败：' + type(e).__name__ + ' ' + str(e)[:160])

    def refresh_async(self):
        def work():
            bid = self._active_id(quiet=True)
            if not bid:
                for k in ('topic', 'reply', 'langdu', 'zhaichao', 'report'):
                    self.vars[k].set('-')
                self.vars['state'].set('未选书')
                self.q.put(('book', {'book_id': 0}))
                self.log('尚未选择书籍：点“读取当前书籍”，或填写书籍 ID 后点“加载 ID”')
                return
            m = {}
            try:
                m = books.meta(bid)
            except Exception as e:
                self.log('读取书籍详情失败：' + str(e)[:160])
                m = books.cached_meta(bid)
            try:
                st = books.status(bid)
            except Exception:
                st = {}
            try:
                c = api.counts(bid)
                self.vars['topic'].set(c['topic'])
                self.vars['reply'].set(c['reply'])
                self.vars['langdu'].set(c['langdu'])
                self.vars['zhaichao'].set(c['zhaichao'])
                self.vars['report'].set(c['report'])
                tg = m.get('targets') or {}
                active = {k: int(v) for k, v in tg.items() if int(v or 0) > 0}
                done = bool(active) and all(c.get(k, 0) >= v for k, v in active.items())
                if c.get('joined') is False:
                    self.vars['state'].set('未加入')
                else:
                    self.vars['state'].set('达标' if done else '进行中')
                self.log('状态已刷新：' + json.dumps(c, ensure_ascii=False))
                joined = c.get('joined')
            except Exception as e:
                self.vars['state'].set('异常')
                self.log('刷新失败：' + str(e)[:200])
                joined = st.get('joined')
            self.q.put(('book', {'book_id': bid, 'title': m.get('title'),
                                 'short_title': m.get('short_title') or st.get('short_title'),
                                 'targets': m.get('targets') or st.get('targets'),
                                 'language': st.get('language') or m.get('language'),
                                 'paragraphs': st.get('paragraphs'), 'joined': joined}))
        threading.Thread(target=work, daemon=True).start()

    def login(self):
        def work():
            try:
                msg = core.login_from_device()
                self.log(msg)
                self._show_account()
                self.refresh_async()
            except Exception as e:
                self.log('读取登录态失败：' + str(e)[:200])
        threading.Thread(target=work, daemon=True).start()

    def _show_account(self, cookie_str=None):
        c = cookie_str if cookie_str is not None else (api.load_cfg().get('cookie') or '')
        label = api.who_label(c)
        if label:
            self.acct_var.set('账号：' + label)
            self.acct_lbl.configure(fg=OK)
        else:
            self.acct_var.set('账号：未登录')
            self.acct_lbl.configure(fg=DIM)

    def _reset_view(self):
        self.targets = {}
        self.joined = None
        for k in ('topic', 'reply', 'langdu', 'zhaichao', 'report'):
            self.vars[k].set('-')
        self.vars['state'].set('未选书')
        self.book_var.set('书籍：未选择（点“读取当前书籍”）')
        self.book_id_var.set('')
        self._last_state = None
        self._update_task_buttons()

    def clear_login(self):
        cur = api.load_cfg().get('cookie') or ''
        label = api.who_label(cur) or '当前账号'
        if not messagebox.askyesno('清除登录态',
                                   '将清除本机保存的登录态（%s）并取消当前书籍选择。\n'
                                   '模拟器里好策 App 的登录不会退出。\n\n'
                                   '换号操作时先清除，再点“读取登录态”，可避免污染旧账号数据。\n\n'
                                   '确定继续？' % label):
            return
        try:
            api.clear_login()
        except Exception as e:
            self.log('清除登录态失败：' + type(e).__name__ + ' ' + str(e)[:200])
            return
        self._show_account('')
        self._reset_view()
        self.log('登录态已清除（原账号 %s），书籍选择已重置' % label)

    def _ensure_login(self):
        if api.load_cfg().get('cookie'):
            return True
        self.log('尚未读取登录态，正在从模拟器获取 Cookie…')
        try:
            self.log(core.login_from_device())
            self._show_account()
            return True
        except Exception as e:
            self.log('自动读取登录态失败：' + type(e).__name__ + ' ' + str(e)[:200])
            self.log('请先点“读取登录态”，并确认好策 App 已登录、adb root 可用')
            return False

    def _run(self, fn):
        def work():
            self.set_busy(True)
            core.STOP.clear()
            try:
                fn(self.log)
            except Exception as e:
                self.log('任务异常：' + type(e).__name__ + ' ' + str(e)[:200])
            finally:
                self.set_busy(False)
                self.refresh_async()
        threading.Thread(target=work, daemon=True).start()

    def run_all(self):
        self._run(core.run_all)

    def run_task(self, name):
        if name == 'langdu':
            self._run(lambda logf: core.run_langdu(None, logf))
        elif name == 'zhaichao':
            self._run(lambda logf: core.run_zhaichao(None, logf))
        else:
            self._run(lambda logf: core.run_taolun(None, None, logf))

    def read_current(self):
        if self.busy:
            self.log('当前已有任务在运行，请先停止')
            return
        self.set_busy(True)

        def work():
            try:
                self.log('正在从模拟器读取当前书籍…')
                info = books.current_book(self.log)
                if not self._ensure_login():
                    self.log('已识别到书籍，但缺少登录态，未切换')
                    return
                books.activate(info['book_id'], info.get('novel_id'), self.log)
                try:
                    res = books.ensure_library(info['book_id'], self.log)
                    self.log('书籍库就绪：%d 段（%s）' % (res.get('paragraphs', 0), res.get('language', '')))
                except Exception as e:
                    self.log('自动建库失败：' + type(e).__name__ + ' ' + str(e)[:200])
                    self.log('可在 App 里确认这本书有 PDF，或用“导入文本”选择 TXT/PDF')
                self._push_book(info['book_id'])
            except Exception as e:
                self.log('读取当前书籍失败：' + type(e).__name__ + ' ' + str(e)[:220])
            finally:
                self.set_busy(False)
                self.refresh_async()
        threading.Thread(target=work, daemon=True).start()

    def load_id(self):
        s = self.book_id_var.get().strip()
        if not s.isdigit() or int(s) <= 0:
            self.log('请输入正确的书籍 ID（详情接口里的 book_id）')
            return
        if self.busy:
            self.log('当前已有任务在运行，请先停止')
            return
        bid = int(s)
        self.set_busy(True)

        def work():
            try:
                if not self._ensure_login():
                    return
                books.activate(bid, None, self.log)
                try:
                    res = books.ensure_library(bid, self.log)
                    self.log('书籍库就绪：%d 段（%s）' % (res.get('paragraphs', 0), res.get('language', '')))
                except Exception as e:
                    self.log('自动建库失败：' + type(e).__name__ + ' ' + str(e)[:200])
                self._push_book(bid)
            except Exception as e:
                self.log('加载书籍失败：' + type(e).__name__ + ' ' + str(e)[:220])
            finally:
                self.set_busy(False)
                self.refresh_async()
        threading.Thread(target=work, daemon=True).start()

    def build_library(self):
        bid = self._active_id()
        if not bid or self.busy:
            if self.busy:
                self.log('当前已有任务在运行，请先停止')
            return
        self.set_busy(True)

        def work():
            try:
                res = books.ensure_library(bid, self.log)
                self.log('书籍库就绪：%d 段（%s）' % (res.get('paragraphs', 0), res.get('language', '')))
                self._push_book(bid)
            except Exception as e:
                self.log('建库失败：' + type(e).__name__ + ' ' + str(e)[:220])
            finally:
                self.set_busy(False)
                self.refresh_async()
        threading.Thread(target=work, daemon=True).start()

    def import_text(self):
        bid = self._active_id()
        if not bid or self.busy:
            if self.busy:
                self.log('当前已有任务在运行，请先停止')
            return
        path = filedialog.askopenfilename(title='选择这本书的 TXT / Markdown / PDF',
                                          filetypes=[('文本或 PDF', '*.txt *.md *.pdf'), ('所有文件', '*.*')])
        if not path:
            return
        self.set_busy(True)

        def work():
            try:
                res = books.import_file(path, bid, self.log)
                self.log('导入完成：%d 段（%s）' % (res.get('paragraphs', 0), res.get('language', '')))
                self._push_book(bid)
            except Exception as e:
                self.log('导入失败：' + type(e).__name__ + ' ' + str(e)[:220])
            finally:
                self.set_busy(False)
                self.refresh_async()
        threading.Thread(target=work, daemon=True).start()

    def _on_page(self, text):
        self.q.put(('page', text))

    def _set_speed(self, val):
        self.speed.set(val)
        for k, b in self.speed_btns.items():
            if k == val:
                b._bg, b._hov, b._fg = BUTTON_STYLES['cyan']
            else:
                b._bg, b._hov, b._fg = BUTTON_STYLES['ghost']
            if str(b['state']) != 'disabled':
                b.configure(bg=b._bg, fg=b._fg)
        self._speed_hint()

    def _speed_hint(self):
        if self.turner:
            return
        name = {'slow': '慢速', 'normal': '正常', 'fast': '快速'}.get(self.speed.get(), '正常')
        self.page_var.set(f'翻页速度：{name}（请先在 App 打开阅读页）')

    def start_turn(self):
        if self.busy:
            self.log('当前已有任务在运行，请先停止')
            return
        try:
            self.turner = turner.PageTurner(self.log, self._on_page)
        except Exception as e:
            self.log('无法启动翻页：' + str(e)[:200])
            return
        self.set_busy(True)
        self.page_var.set('页码：正在定位…')

        def work():
            try:
                self.turner.run(self.speed.get())
            except Exception as e:
                self.log('翻页异常：' + type(e).__name__ + ' ' + str(e)[:200])
            finally:
                self.turner = None
                self.set_busy(False)
                self.page_var.set('页码：-（请先在 App 打开阅读页）')
                self.refresh_async()
        threading.Thread(target=work, daemon=True).start()

    def stop(self):
        core.STOP.set()
        if self.turner:
            self.turner.stop.set()
        self.log('已发送停止信号，当前条目结束后停止')


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        res = {}
        try:
            cfg = api.load_cfg()
            res['pdftotext'] = runtime.find_pdftotext(cfg)
            res['adb'] = runtime.find_adb(cfg)
            res['ffmpeg'] = runtime.find_ffmpeg(cfg)
        except Exception as e:
            res['bin_error'] = type(e).__name__ + ' ' + str(e)[:200]
        try:
            import pypdf
            res['pypdf'] = getattr(pypdf, '__version__', 'ok')
        except Exception as e:
            res['pypdf_error'] = type(e).__name__ + ' ' + str(e)[:200]
        try:
            res['login'] = core.login_from_device()
        except Exception as e:
            res['login_error'] = type(e).__name__ + ' ' + str(e)[:200]
        try:
            info = books.current_book(lambda m: None)
            res['current_book'] = info
            books.activate(info['book_id'], info.get('novel_id'), lambda m: None)
        except Exception as e:
            res['current_book_error'] = type(e).__name__ + ' ' + str(e)[:200]
        try:
            res['status'] = core.status()
        except Exception as e:
            res['status_error'] = type(e).__name__ + ' ' + str(e)[:200]
        try:
            res['library'] = books.status()
        except Exception as e:
            res['library_error'] = type(e).__name__ + ' ' + str(e)[:200]
        try:
            amr = core.make_amr('Packaged self test. The quick brown fox jumps over the lazy dog.', 'selftest')
            res['amr'] = [amr, os.path.getsize(amr)]
        except Exception as e:
            res['amr_error'] = type(e).__name__ + ' ' + str(e)[:200]
        try:
            t = turner.PageTurner(lambda m: None)
            res['page'] = t.stable_page(2)
            if os.environ.get('HAOCE_SELFTEST_TURN') == '1':
                t.run('fast', max_turns=1)
                res['page_after_turn'] = t.stable_page(2)
        except Exception as e:
            res['page_error'] = type(e).__name__ + ' ' + str(e)[:200]
        out = os.path.join(runtime.APP, 'selftest.json')
        json.dump(res, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        sys.exit(0)
    App().mainloop()
