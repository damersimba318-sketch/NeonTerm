"""
NeonTerm — ультра-лёгкий графический эмулятор терминала для Windows.
Стиль: Kitty/Alacritty минимализм.
Зависимости: ТОЛЬКО стандартная библиотека Python (tkinter).
Вес после компиляции Nuitka: ~1-2 МБ.
"""

import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import font as tkfont
import ctypes
import signal

# ─── Цветовая палитра ───────────────────────────────────────────────
COLORS = {
    "bg":           "#0B0D13",
    "fg_output":    "#00FF66",
    "fg_input":     "#00FFFF",
    "fg_prompt":    "#00FFAA",
    "fg_error":     "#FF4466",
    "fg_system":    "#FFAA00",
    "border":       "#00FF66",
    "title_bg":     "#0D0F15",
    "btn_close":    "#FF4466",
    "btn_minimize": "#FFAA00",
    "btn_hover_c":  "#FF1133",
    "btn_hover_m":  "#FFcc33",
    "scrollbar_bg": "#111320",
    "scrollbar_fg": "#00FF66",
    "selection":    "#1A3A2A",
    "cursor_color": "#00FFFF",
}

FONT_FAMILY = "Consolas"
FONT_SIZE = 11
TITLE = "NeonTerm"
BORDER_WIDTH = 1
TITLEBAR_HEIGHT = 32
MIN_WIDTH = 600
MIN_HEIGHT = 400
DEFAULT_WIDTH = 900
DEFAULT_HEIGHT = 560


class NeonTerm:
    """Главный класс эмулятора терминала."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(TITLE)
        self.root.overrideredirect(True)
        self.root.configure(bg=COLORS["border"])
        self.root.geometry(f"{DEFAULT_WIDTH}x{DEFAULT_HEIGHT}")
        self.root.minsize(MIN_WIDTH, MIN_HEIGHT)

        # ─── Состояние ──────────────────────────────────────────
        self.cwd = os.getcwd()
        self.history = []
        self.history_index = -1
        self.running_process = None
        self.is_maximized = False
        self.prev_geometry = None
        self.drag_data = {"x": 0, "y": 0}
        self.resize_data = {"active": False}

        # ─── DPI Awareness (Windows) ────────────────────────────
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        # ─── Иконка окна (встроенная, без файлов) ───────────────
        self._set_icon()

        # ─── Построение UI ──────────────────────────────────────
        self._build_ui()

        # ─── Привязки событий ───────────────────────────────────
        self._bind_events()

        # ─── Приветствие ────────────────────────────────────────
        self._print_welcome()
        self._show_prompt()

        # ─── Фокус на ввод ──────────────────────────────────────
        self.root.after(100, lambda: self.entry.focus_force())

        # ─── Taskbar presence (Windows) ─────────────────────────
        self.root.after(10, self._add_to_taskbar)

    def _set_icon(self):
        """Устанавливает простую иконку через встроенный PhotoImage."""
        try:
            # Создаём крошечную иконку 16x16 программно
            icon = tk.PhotoImage(width=16, height=16)
            for x in range(16):
                for y in range(16):
                    if 2 <= x <= 13 and 2 <= y <= 13:
                        icon.put("#00FF66", (x, y))
                    else:
                        icon.put("#0B0D13", (x, y))
            self.root.iconphoto(True, icon)
        except Exception:
            pass

    def _add_to_taskbar(self):
        """Хак: показывает overrideredirect-окно на панели задач Windows."""
        try:
            import ctypes
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080

            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = style & ~WS_EX_TOOLWINDOW
            style = style | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

            self.root.withdraw()
            self.root.after(50, self.root.deiconify)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    #  UI CONSTRUCTION
    # ═══════════════════════════════════════════════════════════════

    def _build_ui(self):
        """Строит весь интерфейс."""
        # ─── Внутренний контейнер (внутри неоновой рамки) ────────
        self.inner = tk.Frame(self.root, bg=COLORS["bg"])
        self.inner.pack(fill="both", expand=True,
                        padx=BORDER_WIDTH, pady=BORDER_WIDTH)

        self._build_titlebar()
        self._build_terminal_area()
        self._build_input_line()
        self._build_resize_grip()

    def _build_titlebar(self):
        """Кастомный заголовок окна в стиле Linux-терминала."""
        titlebar = tk.Frame(self.inner, bg=COLORS["title_bg"],
                            height=TITLEBAR_HEIGHT)
        titlebar.pack(fill="x", side="top")
        titlebar.pack_propagate(False)

        # Иконка-символ
        icon_label = tk.Label(
            titlebar, text="⬢", fg=COLORS["border"],
            bg=COLORS["title_bg"],
            font=(FONT_FAMILY, 14, "bold")
        )
        icon_label.pack(side="left", padx=(10, 4))

        # Название
        title_label = tk.Label(
            titlebar, text=TITLE, fg="#667788",
            bg=COLORS["title_bg"],
            font=(FONT_FAMILY, 10, "bold")
        )
        title_label.pack(side="left", padx=(2, 0))

        # Путь в заголовке
        self.title_path = tk.Label(
            titlebar, text="", fg="#445566",
            bg=COLORS["title_bg"],
            font=(FONT_FAMILY, 9)
        )
        self.title_path.pack(side="left", padx=(8, 0))

        # ─── Кнопки управления ──────────────────────────────────
        btn_frame = tk.Frame(titlebar, bg=COLORS["title_bg"])
        btn_frame.pack(side="right", padx=(0, 6))

        btn_cfg = {
            "bd": 0, "relief": "flat", "width": 3, "height": 1,
            "font": (FONT_FAMILY, 10, "bold"),
            "bg": COLORS["title_bg"], "activebackground": COLORS["title_bg"]
        }

        # Кнопка закрытия
        self.btn_close = tk.Button(
            btn_frame, text="✕", fg=COLORS["btn_close"],
            activeforeground=COLORS["btn_hover_c"],
            command=self._on_close, **btn_cfg
        )
        self.btn_close.pack(side="right", padx=1)
        self.btn_close.bind("<Enter>",
                            lambda e: self.btn_close.config(fg=COLORS["btn_hover_c"]))
        self.btn_close.bind("<Leave>",
                            lambda e: self.btn_close.config(fg=COLORS["btn_close"]))

        # Кнопка максимизации
        self.btn_max = tk.Button(
            btn_frame, text="□", fg="#556677",
            activeforeground="#88AACC",
            command=self._toggle_maximize, **btn_cfg
        )
        self.btn_max.pack(side="right", padx=1)
        self.btn_max.bind("<Enter>",
                          lambda e: self.btn_max.config(fg="#88AACC"))
        self.btn_max.bind("<Leave>",
                          lambda e: self.btn_max.config(fg="#556677"))

        # Кнопка сворачивания
        self.btn_min = tk.Button(
            btn_frame, text="─", fg=COLORS["btn_minimize"],
            activeforeground=COLORS["btn_hover_m"],
            command=self._minimize, **btn_cfg
        )
        self.btn_min.pack(side="right", padx=1)
        self.btn_min.bind("<Enter>",
                          lambda e: self.btn_min.config(fg=COLORS["btn_hover_m"]))
        self.btn_min.bind("<Leave>",
                          lambda e: self.btn_min.config(fg=COLORS["btn_minimize"]))

        # ─── Перетаскивание окна ────────────────────────────────
        for widget in [titlebar, icon_label, title_label, self.title_path]:
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._do_drag)
            widget.bind("<Double-Button-1>", lambda e: self._toggle_maximize())

        self.titlebar = titlebar

    def _build_terminal_area(self):
        """Основная текстовая область вывода."""
        text_frame = tk.Frame(self.inner, bg=COLORS["bg"])
        text_frame.pack(fill="both", expand=True, padx=6, pady=(2, 0))

        # Скроллбар
        self.scrollbar = tk.Scrollbar(
            text_frame,
            bg=COLORS["scrollbar_bg"],
            troughcolor=COLORS["bg"],
            activebackground=COLORS["scrollbar_fg"],
            highlightthickness=0,
            bd=0,
            width=8
        )
        self.scrollbar.pack(side="right", fill="y")

        # Текстовое поле
        self.output = tk.Text(
            text_frame,
            bg=COLORS["bg"],
            fg=COLORS["fg_output"],
            insertbackground=COLORS["cursor_color"],
            selectbackground=COLORS["selection"],
            selectforeground=COLORS["fg_output"],
            font=(FONT_FAMILY, FONT_SIZE, "bold"),
            wrap="word",
            bd=0,
            padx=8,
            pady=6,
            relief="flat",
            state="disabled",
            cursor="arrow",
            yscrollcommand=self.scrollbar.set
        )
        self.output.pack(fill="both", expand=True)
        self.scrollbar.config(command=self.output.yview)

        # ─── Теги для цветного вывода ───────────────────────────
        self.output.tag_configure("prompt",
                                  foreground=COLORS["fg_prompt"],
                                  font=(FONT_FAMILY, FONT_SIZE, "bold"))
        self.output.tag_configure("command",
                                  foreground=COLORS["fg_input"],
                                  font=(FONT_FAMILY, FONT_SIZE, "bold"))
        self.output.tag_configure("output",
                                  foreground=COLORS["fg_output"],
                                  font=(FONT_FAMILY, FONT_SIZE))
        self.output.tag_configure("error",
                                  foreground=COLORS["fg_error"],
                                  font=(FONT_FAMILY, FONT_SIZE))
        self.output.tag_configure("system",
                                  foreground=COLORS["fg_system"],
                                  font=(FONT_FAMILY, FONT_SIZE, "bold"))

    def _build_input_line(self):
        """Строка ввода команд."""
        input_frame = tk.Frame(self.inner, bg=COLORS["bg"])
        input_frame.pack(fill="x", side="bottom", padx=6, pady=(2, 6))

        # Разделительная линия
        separator = tk.Frame(input_frame, bg=COLORS["border"], height=1)
        separator.pack(fill="x", pady=(0, 4))

        # Контейнер для prompt + entry
        line_frame = tk.Frame(input_frame, bg=COLORS["bg"])
        line_frame.pack(fill="x")

        # Prompt label
        self.prompt_label = tk.Label(
            line_frame,
            text=self._make_prompt(),
            fg=COLORS["fg_prompt"],
            bg=COLORS["bg"],
            font=(FONT_FAMILY, FONT_SIZE, "bold"),
            anchor="w"
        )
        self.prompt_label.pack(side="left")

        # Entry
        self.entry = tk.Entry(
            line_frame,
            bg=COLORS["bg"],
            fg=COLORS["fg_input"],
            insertbackground=COLORS["cursor_color"],
            selectbackground=COLORS["selection"],
            selectforeground=COLORS["fg_input"],
            font=(FONT_FAMILY, FONT_SIZE, "bold"),
            bd=0,
            relief="flat"
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(2, 0))

    def _build_resize_grip(self):
        """Невидимые зоны для ресайза окна."""
        grip = tk.Label(
            self.inner, text="◢", fg="#223344",
            bg=COLORS["bg"],
            font=(FONT_FAMILY, 10),
            cursor="size_nw_se"
        )
        grip.place(relx=1.0, rely=1.0, anchor="se")
        grip.bind("<Button-1>", self._start_resize)
        grip.bind("<B1-Motion>", self._do_resize)

        # Резайз-зоны по краям
        edges = {
            "right":  {"cursor": "size_we",  "relx": 1.0, "rely": 0.5,
                       "anchor": "e", "width": 4, "relheight": 1.0},
            "bottom": {"cursor": "size_ns",  "relx": 0.5, "rely": 1.0,
                       "anchor": "s", "height": 4, "relwidth": 1.0},
            "left":   {"cursor": "size_we",  "relx": 0.0, "rely": 0.5,
                       "anchor": "w", "width": 4, "relheight": 1.0},
            "top":    {"cursor": "size_ns",  "relx": 0.5, "rely": 0.0,
                       "anchor": "n", "height": 4, "relwidth": 1.0},
        }

        for side, cfg in edges.items():
            cursor = cfg.pop("cursor")
            edge = tk.Frame(self.root, bg=COLORS["border"],
                            cursor=cursor)
            edge.place(**cfg)
            edge.bind("<Button-1>",
                      lambda e, s=side: self._start_edge_resize(e, s))
            edge.bind("<B1-Motion>",
                      lambda e, s=side: self._do_edge_resize(e, s))

    # ═══════════════════════════════════════════════════════════════
    #  EVENT BINDINGS
    # ═══════════════════════════════════════════════════════════════

    def _bind_events(self):
        """Привязка всех событий."""
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Up>", self._history_up)
        self.entry.bind("<Down>", self._history_down)
        self.entry.bind("<Tab>", self._tab_complete)
        self.entry.bind("<Escape>", lambda e: self.entry.delete(0, "end"))

        # Ctrl+C для прерывания процесса
        self.entry.bind("<Control-c>", self._interrupt_process)
        self.root.bind("<Control-c>", self._interrupt_process)

        # Ctrl+L для очистки
        self.entry.bind("<Control-l>", self._clear_screen)
        self.root.bind("<Control-l>", self._clear_screen)

        # Клик по выводу — фокус обратно на ввод
        self.output.bind("<Button-1>",
                         lambda e: self.root.after(10, self.entry.focus_force))

        # Прокрутка мышью
        self.output.bind("<MouseWheel>", self._on_mousewheel)
        self.entry.bind("<MouseWheel>", self._on_mousewheel)

    # ═══════════════════════════════════════════════════════════════
    #  WINDOW MANAGEMENT
    # ═══════════════════════════════════════════════════════════════

    def _start_drag(self, event):
        if self.is_maximized:
            return
        self.drag_data["x"] = event.x_root - self.root.winfo_x()
        self.drag_data["y"] = event.y_root - self.root.winfo_y()

    def _do_drag(self, event):
        if self.is_maximized:
            return
        x = event.x_root - self.drag_data["x"]
        y = event.y_root - self.drag_data["y"]
        self.root.geometry(f"+{x}+{y}")

    def _start_resize(self, event):
        self.resize_data = {
            "active": True,
            "x": event.x_root,
            "y": event.y_root,
            "w": self.root.winfo_width(),
            "h": self.root.winfo_height()
        }

    def _do_resize(self, event):
        dx = event.x_root - self.resize_data["x"]
        dy = event.y_root - self.resize_data["y"]
        new_w = max(MIN_WIDTH, self.resize_data["w"] + dx)
        new_h = max(MIN_HEIGHT, self.resize_data["h"] + dy)
        self.root.geometry(f"{new_w}x{new_h}")

    def _start_edge_resize(self, event, side):
        self.resize_data = {
            "active": True,
            "side": side,
            "x": event.x_root,
            "y": event.y_root,
            "w": self.root.winfo_width(),
            "h": self.root.winfo_height(),
            "root_x": self.root.winfo_x(),
            "root_y": self.root.winfo_y()
        }

    def _do_edge_resize(self, event, side):
        d = self.resize_data
        dx = event.x_root - d["x"]
        dy = event.y_root - d["y"]

        x, y, w, h = d["root_x"], d["root_y"], d["w"], d["h"]

        if side == "right":
            w = max(MIN_WIDTH, d["w"] + dx)
        elif side == "bottom":
            h = max(MIN_HEIGHT, d["h"] + dy)
        elif side == "left":
            new_w = max(MIN_WIDTH, d["w"] - dx)
            if new_w != d["w"] or dx != 0:
                x = d["root_x"] + (d["w"] - new_w)
                w = new_w
        elif side == "top":
            new_h = max(MIN_HEIGHT, d["h"] - dy)
            if new_h != d["h"] or dy != 0:
                y = d["root_y"] + (d["h"] - new_h)
                h = new_h

        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _toggle_maximize(self):
        if self.is_maximized:
            if self.prev_geometry:
                self.root.geometry(self.prev_geometry)
            self.is_maximized = False
            self.btn_max.config(text="□")
        else:
            self.prev_geometry = self.root.geometry()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            # Учитываем панель задач (~40px)
            self.root.geometry(f"{sw}x{sh - 40}+0+0")
            self.is_maximized = True
            self.btn_max.config(text="❐")

    def _minimize(self):
        self.root.withdraw()
        self.root.after(200, lambda: self.root.iconify())
        self.root.after(250, lambda: self.root.deiconify)
        # Альтернативный способ свернуть overrideredirect окно
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
        except Exception:
            self.root.iconify()

    def _on_close(self):
        self._kill_process()
        self.root.destroy()

    def _on_mousewheel(self, event):
        self.output.yview_scroll(-1 * (event.delta // 120), "units")
        return "break"

    # ═══════════════════════════════════════════════════════════════
    #  TERMINAL LOGIC
    # ═══════════════════════════════════════════════════════════════

    def _make_prompt(self):
        """Создаёт строку приглашения в стиле Linux."""
        folder = os.path.basename(self.cwd) or self.cwd
        return f"➜ [{folder}] $ "

    def _update_prompt(self):
        """Обновляет prompt после смены директории."""
        self.prompt_label.config(text=self._make_prompt())
        # Обновляем путь в заголовке
        display_path = self.cwd.replace("\\", "/")
        self.title_path.config(text=f"  ~{display_path}")

    def _show_prompt(self):
        """Показывает prompt в текстовом поле вывода."""
        self._append_text(self._make_prompt(), "prompt")

    def _print_welcome(self):
        """Приветственное сообщение."""
        welcome = (
            "╔══════════════════════════════════════════════╗\n"
            "║         ⬢  N E O N T E R M  v1.0           ║\n"
            "║   Ultra-lightweight terminal emulator        ║\n"
            "║   Type 'help' for built-in commands          ║\n"
            "╚══════════════════════════════════════════════╝\n\n"
        )
        self._append_text(welcome, "system")

    def _append_text(self, text, tag="output"):
        """Потокобезопасная вставка текста в вывод."""
        self.output.config(state="normal")
        self.output.insert("end", text, tag)
        self.output.see("end")
        self.output.config(state="disabled")

    def _safe_append(self, text, tag="output"):
        """Вызывается из фонового потока — планирует вставку в главный поток."""
        self.root.after(0, self._append_text, text, tag)

    def _on_enter(self, event):
        """Обработка нажатия Enter."""
        cmd = self.entry.get().strip()
        self.entry.delete(0, "end")

        if not cmd:
            self._append_text("\n")
            self._show_prompt()
            return

        # Сохраняем в историю
        if not self.history or self.history[-1] != cmd:
            self.history.append(cmd)
        self.history_index = len(self.history)

        # Отображаем введённую команду
        self._append_text(cmd + "\n", "command")

        # Обработка встроенных команд
        if self._handle_builtin(cmd):
            return

        # Запуск внешней команды в отдельном потоке
        self._run_command(cmd)

    def _handle_builtin(self, cmd):
        """Обработка встроенных команд. Возвращает True если обработано."""
        parts = cmd.split(None, 1)
        command = parts[0].lower()

        # ─── CD ─────────────────────────────────────────────────
        if command == "cd":
            path = parts[1] if len(parts) > 1 else os.path.expanduser("~")
            path = path.strip('"').strip("'")

            # Обработка ~ как домашнего каталога
            if path.startswith("~"):
                path = os.path.expanduser(path)

            # Обработка .. и относительных путей
            if not os.path.isabs(path):
                path = os.path.join(self.cwd, path)

            path = os.path.normpath(path)

            if os.path.isdir(path):
                self.cwd = path
                os.chdir(self.cwd)
                self._update_prompt()
            else:
                self._append_text(
                    f"cd: no such directory: {parts[1] if len(parts) > 1 else ''}\n",
                    "error"
                )
            self._show_prompt()
            return True

        # ─── CLEAR / CLS ───────────────────────────────────────
        if command in ("clear", "cls"):
            self._clear_screen()
            return True

        # ─── EXIT ───────────────────────────────────────────────
        if command in ("exit", "quit"):
            self._on_close()
            return True

        # ─── PWD ────────────────────────────────────────────────
        if command == "pwd":
            self._append_text(self.cwd + "\n", "output")
            self._show_prompt()
            return True

        # ─── HELP ───────────────────────────────────────────────
        if command == "help":
            help_text = (
                "\n  ╔═ Built-in Commands ════════════════════╗\n"
                "  ║  cd <path>     Change directory         ║\n"
                "  ║  pwd           Print working directory   ║\n"
                "  ║  clear/cls     Clear terminal screen     ║\n"
                "  ║  exit/quit     Close NeonTerm            ║\n"
                "  ║  help          Show this help            ║\n"
                "  ╠═ Shortcuts ══════════════════════════════╣\n"
                "  ║  Ctrl+C        Interrupt running process ║\n"
                "  ║  Ctrl+L        Clear screen              ║\n"
                "  ║  Tab           Auto-complete paths        ║\n"
                "  ║  Up/Down       Command history           ║\n"
                "  ║  Escape        Clear input line           ║\n"
                "  ╚══════════════════════════════════════════╝\n\n"
            )
            self._append_text(help_text, "system")
            self._show_prompt()
            return True

        return False

    def _run_command(self, cmd):
        """Запускает системную команду в фоновом потоке."""
        thread = threading.Thread(
            target=self._execute_in_thread,
            args=(cmd,),
            daemon=True
        )
        thread.start()

    def _execute_in_thread(self, cmd):
        """Выполняет команду в отдельном потоке с перехватом вывода."""
        try:
            # Определяем кодировку консоли Windows
            encoding = "cp866"

            # Специальная обработка некоторых команд
            # Превращаем ls в dir для Windows
            if cmd.strip() == "ls":
                cmd = "dir /B"
            elif cmd.strip().startswith("ls "):
                cmd = "dir /B " + cmd[3:]

            self.running_process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                cwd=self.cwd,
                creationflags=subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            )

            # Читаем stdout в реальном времени
            for line in iter(self.running_process.stdout.readline, b""):
                if self.running_process is None:
                    break
                try:
                    decoded = line.decode(encoding, errors="replace")
                except Exception:
                    decoded = line.decode("utf-8", errors="replace")
                self._safe_append(decoded, "output")

            # Читаем stderr
            stderr_data = self.running_process.stderr.read()
            if stderr_data:
                try:
                    err_text = stderr_data.decode(encoding, errors="replace")
                except Exception:
                    err_text = stderr_data.decode("utf-8", errors="replace")
                self._safe_append(err_text, "error")

            self.running_process.wait()

        except FileNotFoundError:
            self._safe_append(
                f"'{cmd.split()[0]}': command not found\n", "error"
            )
        except Exception as e:
            self._safe_append(f"Error: {str(e)}\n", "error")
        finally:
            self.running_process = None
            self.root.after(0, self._show_prompt)

    def _interrupt_process(self, event=None):
        """Прерывание текущего процесса (Ctrl+C)."""
        if self.running_process:
            try:
                self.running_process.terminate()
                self.running_process.kill()
            except Exception:
                pass
            self.running_process = None
            self._append_text("\n^C\n", "error")
            self._show_prompt()
            return "break"
        else:
            # Если нет процесса — очищаем строку ввода
            self.entry.delete(0, "end")
            return "break"

    def _kill_process(self):
        """Убивает процесс при закрытии окна."""
        if self.running_process:
            try:
                self.running_process.terminate()
                self.running_process.kill()
            except Exception:
                pass

    def _clear_screen(self, event=None):
        """Очищает экран терминала."""
        self.output.config(state="normal")
        self.output.delete("1.0", "end")
        self.output.config(state="disabled")
        self._show_prompt()
        return "break"

    # ═══════════════════════════════════════════════════════════════
    #  HISTORY & AUTOCOMPLETE
    # ═══════════════════════════════════════════════════════════════

    def _history_up(self, event):
        """Навигация по истории вверх."""
        if self.history and self.history_index > 0:
            self.history_index -= 1
            self.entry.delete(0, "end")
            self.entry.insert(0, self.history[self.history_index])
        return "break"

    def _history_down(self, event):
        """Навигация по истории вниз."""
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.entry.delete(0, "end")
            self.entry.insert(0, self.history[self.history_index])
        elif self.history_index >= len(self.history) - 1:
            self.history_index = len(self.history)
            self.entry.delete(0, "end")
        return "break"

    def _tab_complete(self, event):
        """Автодополнение путей по Tab."""
        text = self.entry.get()
        if not text:
            return "break"

        parts = text.rsplit(" ", 1)
        prefix = parts[-1] if parts else text
        cmd_prefix = parts[0] + " " if len(parts) > 1 else ""

        # Разбираем путь
        if os.path.sep in prefix or "/" in prefix:
            search_dir = os.path.dirname(prefix) or "."
            search_prefix = os.path.basename(prefix)
        else:
            search_dir = "."
            search_prefix = prefix

        # Ищем в текущей директории
        try:
            search_path = os.path.join(self.cwd, search_dir)
            entries = os.listdir(search_path)
            matches = [
                e for e in entries
                if e.lower().startswith(search_prefix.lower())
            ]
        except OSError:
            matches = []

        if len(matches) == 1:
            # Единственное совпадение — дополняем
            match = matches[0]
            full_path = os.path.join(search_dir, match) if search_dir != "." else match
            if os.path.isdir(os.path.join(self.cwd, full_path)):
                full_path += os.path.sep

            self.entry.delete(0, "end")
            self.entry.insert(0, cmd_prefix + full_path)
        elif len(matches) > 1:
            # Несколько совпадений — показываем список
            self._append_text("\n", "output")
            # Находим общий префикс
            common = os.path.commonprefix(matches)

            # Показываем варианты в колонках
            cols = max(1, 80 // (max(len(m) for m in matches) + 2))
            for i, m in enumerate(sorted(matches)):
                is_dir = os.path.isdir(
                    os.path.join(self.cwd, search_dir, m)
                )
                suffix = "/" if is_dir else ""
                tag = "system" if is_dir else "output"
                self._append_text(f"  {m}{suffix:<20s}", tag)
                if (i + 1) % cols == 0:
                    self._append_text("\n")
            self._append_text("\n")
            self._show_prompt()

            # Дополняем общим префиксом
            if common and len(common) > len(search_prefix):
                full_path = (os.path.join(search_dir, common)
                             if search_dir != "." else common)
                self.entry.delete(0, "end")
                self.entry.insert(0, cmd_prefix + full_path)

        return "break"

    # ═══════════════════════════════════════════════════════════════
    #  RUN
    # ═══════════════════════════════════════════════════════════════

    def run(self):
        """Запуск главного цикла."""
        # Центрируем окно
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - DEFAULT_WIDTH) // 2
        y = (sh - DEFAULT_HEIGHT) // 2
        self.root.geometry(f"{DEFAULT_WIDTH}x{DEFAULT_HEIGHT}+{x}+{y}")

        self._update_prompt()
        self.root.mainloop()


# ═══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = NeonTerm()
    app.run()