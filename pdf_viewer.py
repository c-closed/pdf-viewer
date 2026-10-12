"""가벼운 PDF 뷰어 (단일 파일).

의존성: pypdfium2, Pillow (+선택 tkinterdnd2)
기능: 열기/드래그앤드롭, 페이지 이동, 확대/축소, 폭/쪽 맞춤, 회전,
      보기 방식(한쪽/두쪽/n쪽씩) + 보기 단위(페이지/연속 스크롤), 텍스트 검색
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import pypdfium2 as pdfium
from PIL import ImageTk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    _BASE = TkinterDnD.Tk
    DND = True
except Exception:  # 미설치 시 드래그 앤 드롭만 비활성
    DND_FILES = None
    _BASE = tk.Tk
    DND = False

PDF_TYPES = [("PDF 파일", "*.pdf"), ("모든 파일", "*.*")]
MIN_ZOOM, MAX_ZOOM = 0.1, 8.0
GAP = 16  # 페이지 사이 간격(px)

COLS_CHOICES = [1, 2, 3, 4, 5, 6]
MAX_COLS = 12

# 앱 버전(단일 소스). build.ps1이 이 값을 읽어 설치 파일 버전으로 전달한다.
__version__ = "1.2.1"

# 자동 업데이트: GitHub Releases가 제공하는 최신 버전 manifest 주소
UPDATE_MANIFEST_URL = "https://github.com/c-closed/pdf-viewer/releases/latest/download/latest.json"


def _cols_label(n: int) -> str:
    return f"{int(n)}쪽씩"


UNIT_LABELS = {"페이지": False, "연속": True}

DEFAULT_SETTINGS = {"view_cols": 1, "view_continuous": False,
                    "start_fit": "width", "zoom_pct": 100, "auto_update": True}


def _settings_path() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "PDFViewer", "settings.json")


def _load_settings() -> dict:
    try:
        with open(_settings_path(), encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return dict(DEFAULT_SETTINGS)
    s = {**DEFAULT_SETTINGS, **data}
    # 예전 view_mode(single/two/continuous) → view_cols/view_continuous 마이그레이션
    if "view_cols" not in data and "view_mode" in data:
        old = data.get("view_mode")
        if old == "two":
            s["view_cols"], s["view_continuous"] = 2, False
        elif old == "continuous":
            s["view_cols"], s["view_continuous"] = 1, True
        else:
            s["view_cols"], s["view_continuous"] = 1, False
    s.pop("view_mode", None)
    return s


def _save_settings(data: dict) -> bool:
    try:
        d = os.path.dirname(_settings_path())
        os.makedirs(d, exist_ok=True)
        with open(_settings_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _icon_path(name: str) -> str:
    """번들/소스 실행 환경 모두에서 아이콘 경로를 찾는다."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, name)


PROGID = "PDFViewer.pdf"
CAP_NAME = "PDFViewer"


def _app_exe() -> str:
    """연결 대상 실행 파일 경로(설치본은 exe, 소스는 python 스크립트)."""
    if getattr(sys, "frozen", False):
        return os.path.abspath(sys.executable)
    return os.path.abspath(sys.argv[0])


def _reg_set(path: str, name: str, value, typ) -> None:
    import winreg

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, typ, value)


def _notify_shell() -> None:
    """탐색기에 파일 연결 변경을 알린다."""
    try:
        import ctypes

        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, 0, 0)
    except Exception:
        pass


def register_pdf_association(exe: str, base: str = "Software") -> None:
    """PDF 뷰어를 .pdf 연결 프로그램(ProgID/기본앱 목록)으로 등록한다."""
    import winreg

    classes = base + r"\Classes"
    prog = classes + "\\" + PROGID
    _reg_set(prog, "", "PDF 문서", winreg.REG_SZ)
    _reg_set(prog + r"\DefaultIcon", "", f'"{exe}",0', winreg.REG_SZ)
    _reg_set(prog + r"\shell\open\command", "", f'"{exe}" "%1"', winreg.REG_SZ)
    _reg_set(prog + r"\Application", "ApplicationName", "PDF Viewer", winreg.REG_SZ)
    _reg_set(prog + r"\Application", "ApplicationCompany", "류호준", winreg.REG_SZ)
    # 실행 파일 단위 등록 (기본 앱/연결 프로그램 목록의 이름·아이콘)
    appk = classes + r"\Applications\\" + os.path.basename(exe)
    _reg_set(appk, "FriendlyAppName", "PDF Viewer", winreg.REG_SZ)
    _reg_set(appk, "ApplicationCompany", "류호준", winreg.REG_SZ)
    _reg_set(appk + r"\DefaultIcon", "", f'"{exe}",0', winreg.REG_SZ)
    _reg_set(appk + r"\shell\open\command", "", f'"{exe}" "%1"', winreg.REG_SZ)
    _reg_set(appk + r"\SupportedTypes", ".pdf", "", winreg.REG_SZ)
    # '연결 프로그램' 목록에 추가
    _reg_set(classes + r"\.pdf\OpenWithProgids", PROGID, b"", winreg.REG_NONE)
    # Windows '기본 앱' 목록에 표시되도록 Capabilities 등록
    caps = base + r"\PDFViewer\Capabilities"
    _reg_set(caps, "", "PDF Viewer", winreg.REG_SZ)
    _reg_set(caps, "ApplicationName", "PDF Viewer", winreg.REG_SZ)
    _reg_set(caps, "ApplicationDescription", "가벼운 PDF 뷰어", winreg.REG_SZ)
    _reg_set(caps + r"\FileAssociations", ".pdf", PROGID, winreg.REG_SZ)
    _reg_set(base + r"\RegisteredApplications", CAP_NAME, base + r"\PDFViewer\Capabilities",
             winreg.REG_SZ)


def set_default_pdf_app() -> tuple[bool, str]:
    """설치된 실행 파일을 PDF 기본 프로그램으로 설정한다."""
    if not getattr(sys, "frozen", False):
        return False, ("설치된 실행 파일(설치 버전)에서만 기본 프로그램으로 설정할 수 있습니다.")
    try:
        import winreg
    except Exception:
        return False, "레지스트리를 사용할 수 없는 환경입니다."

    exe = _app_exe()
    try:
        register_pdf_association(exe)
        # 기존 사용자 선택(UserChoice)이 남아 있으면 기본값 변경이 무시되므로 제거 시도
        try:
            winreg.DeleteKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.pdf\UserChoice",
            )
        except OSError:
            pass
        _reg_set(r"Software\Classes\.pdf", "", PROGID, winreg.REG_SZ)
        _notify_shell()
        return True, ("PDF 기본 프로그램으로 등록했습니다.\n"
                      "Windows 10/11에서는 '기본 앱' 설정에서 한 번 더 확인해야 할 수 있습니다.")
    except Exception as e:  # noqa: BLE001
        return False, f"등록 실패: {e}"


def open_default_apps_settings() -> None:
    """Windows '기본 앱' 설정 화면을 연다."""
    try:
        os.startfile("ms-settings:defaultapps")  # noqa: S606
    except Exception:
        pass


# ---------------------------------------------------------------------- #
# 무음 자동 업데이트
# ---------------------------------------------------------------------- #
def _version_tuple(v) -> tuple:
    nums = re.findall(r"\d+", str(v))
    return tuple(int(n) for n in nums[:3]) + (0,) * max(0, 3 - len(nums))


def fetch_update_info() -> dict | None:
    """GitHub Releases의 최신 manifest(latest.json)를 조회한다."""
    import urllib.request

    req = urllib.request.Request(
        UPDATE_MANIFEST_URL,
        headers={"User-Agent": f"PDFViewer/{__version__}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=8) as r:
        data = json.loads(r.read().decode("utf-8"))
    if not isinstance(data, dict) or not data.get("version") or not data.get("url"):
        return None
    return data


def download_update(info: dict) -> str | None:
    """설치 파일을 받아 sha256을 검증하고 임시 경로를 돌려준다."""
    import hashlib
    import tempfile
    import urllib.request

    url = str(info.get("url"))
    fd, path = tempfile.mkstemp(prefix="PDFViewer-Setup-", suffix=".exe")
    os.close(fd)
    digest = hashlib.sha256()
    req = urllib.request.Request(url, headers={"User-Agent": f"PDFViewer/{__version__}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
                digest.update(chunk)
    except Exception:
        _safe_remove(path)
        return None
    want = str(info.get("sha256") or "").strip().lower()
    if want and digest.hexdigest().lower() != want:
        _safe_remove(path)
        return None
    return path


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def launch_silent_update(installer: str, relaunch: str) -> bool:
    """무음 설치를 실행하고, 끝나면 앱을 다시 시작한다(현재 앱은 곧 종료)."""
    cmd = (
        'ping -n 2 127.0.0.1 > nul & '
        f'start "" /wait "{installer}" /VERYSILENT /NORESTART /SUPPRESSMSGBOXES /CLOSEAPPLICATIONS '
        f'& start "" "{relaunch}"'
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.Popen(cmd, shell=True, creationflags=flags, close_fds=True)
        return True
    except Exception:
        return False


class PdfViewer(_BASE):
    def __init__(self, path: str | None = None):
        super().__init__()
        self.title("PDF 뷰어")
        self.geometry("960x800")
        self.minsize(520, 400)

        ico = _icon_path("icon.ico")
        if os.path.exists(ico):
            try:
                self.iconbitmap(ico)
            except Exception:
                pass

        self.pdf: pdfium.PdfDocument | None = None
        self.path: str | None = None
        self.index = 0
        self.zoom = 1.0
        self.rotation = 0
        self.settings = _load_settings()
        self.cols = max(1, int(self.settings.get("view_cols", 1)))     # 가로로 보일 페이지 수
        self.continuous = bool(self.settings.get("view_continuous", False))  # 연속 스크롤 여부
        self._fit: str | None = None  # 창 크기에 따라 자동 재맞춤(width/page)

        self._placed: dict[int, int] = {}      # page -> canvas item id
        self._photos: dict[int, object] = {}   # page -> PhotoImage
        self._layout: dict[int, tuple] = {}    # page -> (x, y, w, h) px
        self._content_w = 1.0
        self._total_h = 1.0
        self._natural_w = 1.0   # 연속 보기: 페이지들이 차지하는 실제 폭
        self._natural_h = 1.0   # 연속 보기: 페이지들이 차지하는 실제 높이
        self._cont_offx = 0.0   # 연속 보기: 가로 가운데 정렬 오프셋
        self._cont_offy = 0.0   # 연속 보기: 세로 가운데 정렬 오프셋

        self._matches: list = []               # [(page, (l,b,r,t))]
        self._matches_by_page: dict = {}       # page -> [(global_idx, rect)]
        self.match_pos = 0

        self._resize_job = None
        self._build()
        self._bind_keys()

        if getattr(sys, "frozen", False) and self.settings.get("auto_update", True):
            threading.Thread(target=self._update_worker, daemon=True).start()

        if path:
            self.after(80, lambda: self.open_file(path))

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #
    def _build(self):
        bar = ttk.Frame(self, padding=6)
        bar.pack(side="top", fill="x")

        ttk.Button(bar, text="열기", command=self.on_open).pack(side="left")
        ttk.Button(bar, text="설정", command=self._open_settings).pack(side="left", padx=(6, 0))

        # 검색 (오른쪽)
        sbox = ttk.Frame(bar)
        sbox.pack(side="right")
        ttk.Label(sbox, text="검색").pack(side="left")
        self.search_var = tk.StringVar()
        sent = ttk.Entry(sbox, textvariable=self.search_var, width=32)
        sent.pack(side="left", padx=4)
        sent.bind("<Return>", lambda e: self.do_search())
        ttk.Button(sbox, text="찾기", command=self.do_search).pack(side="left")
        ttk.Button(sbox, text="‹", width=3, command=self.prev_match).pack(side="left", padx=(6, 0))
        ttk.Button(sbox, text="›", width=3, command=self.next_match).pack(side="left")
        self.search_info = tk.StringVar(value="0/0")
        ttk.Label(sbox, textvariable=self.search_info).pack(side="left", padx=6)

        # 하단 컨트롤 바 (페이지 이동 / 배율 / 보기 방식·단위)
        cbar = ttk.Frame(self, padding=(6, 4))
        cbar.pack(side="bottom", fill="x")
        ttk.Button(cbar, text="◀", width=3, command=self.prev_page).pack(side="left")
        self.page_var = tk.StringVar(value="0")
        ent = ttk.Entry(cbar, textvariable=self.page_var, width=5, justify="center")
        ent.pack(side="left", padx=2)
        ent.bind("<Return>", self.on_page_jump)
        self.total_var = tk.StringVar(value="/ 0")
        ttk.Label(cbar, textvariable=self.total_var).pack(side="left")
        ttk.Button(cbar, text="▶", width=3, command=self.next_page).pack(side="left", padx=(2, 12))

        ttk.Separator(cbar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(cbar, text="－", width=3, command=lambda: self.zoom_by(1 / 1.25)).pack(side="left")
        self.zoom_var = tk.StringVar(value="100%")
        ttk.Label(cbar, textvariable=self.zoom_var, width=6, anchor="center").pack(side="left")
        ttk.Button(cbar, text="＋", width=3, command=lambda: self.zoom_by(1.25)).pack(side="left", padx=(2, 12))

        ttk.Button(cbar, text="폭 맞춤", command=self.fit_width).pack(side="left", padx=2)
        ttk.Button(cbar, text="쪽 맞춤", command=self.fit_page).pack(side="left", padx=2)
        ttk.Button(cbar, text="회전", command=self.rotate).pack(side="left", padx=(2, 6))

        ttk.Separator(cbar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Label(cbar, text="보기").pack(side="left", padx=(0, 4))
        self.cols_n_var = tk.StringVar(value=str(self.cols))
        spin = ttk.Spinbox(cbar, from_=1, to=MAX_COLS, width=4,
                           textvariable=self.cols_n_var, command=self._on_cols_n)
        spin.pack(side="left")
        spin.bind("<Return>", self._on_cols_n)
        spin.bind("<FocusOut>", self._on_cols_n)
        ttk.Label(cbar, text="쪽씩").pack(side="left", padx=(2, 10))

        ttk.Label(cbar, text="단위").pack(side="left", padx=(0, 4))
        self.unit_var = tk.StringVar(value="연속" if self.continuous else "페이지")
        ub = ttk.Combobox(cbar, textvariable=self.unit_var, values=list(UNIT_LABELS),
                          width=5, state="readonly")
        ub.pack(side="left")
        ub.bind("<<ComboboxSelected>>",
                lambda e: self.set_view(continuous=UNIT_LABELS[self.unit_var.get()]))

        # 본문 캔버스
        body = ttk.Frame(self)
        body.pack(side="top", fill="both", expand=True)
        self.canvas = tk.Canvas(body, bg="#3a3a3a", highlightthickness=0)
        self.vsb = ttk.Scrollbar(body, orient="vertical", command=self._on_scrollbar)
        hsb = ttk.Scrollbar(body, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.vsb.set, xscrollcommand=hsb.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        self.canvas.bind("<MouseWheel>", self.on_wheel)
        self.canvas.bind("<Button-4>", lambda e: self._scroll_units(-1))
        self.canvas.bind("<Button-5>", lambda e: self._scroll_units(1))
        self.canvas.bind("<ButtonPress-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.do_pan)
        self.canvas.bind("<Configure>", self.on_configure)

        if DND:
            for w in (self, self.canvas):
                try:
                    w.drop_target_register(DND_FILES)
                    w.dnd_bind("<<Drop>>", self.on_drop)
                except Exception:
                    pass

    def _bind_keys(self):
        b = self.bind
        b("<Control-o>", lambda e: self.on_open())
        b("<Control-f>", lambda e: self.search_var and self.focus_set())
        b("<Right>", lambda e: self.next_page())
        b("<Down>", lambda e: self.next_page())
        b("<Next>", lambda e: self.next_page())
        b("<space>", lambda e: self.next_page())
        b("<Left>", lambda e: self.prev_page())
        b("<Up>", lambda e: self.prev_page())
        b("<Prior>", lambda e: self.prev_page())
        b("<Home>", lambda e: self.goto(0))
        b("<End>", lambda e: self.goto(10 ** 9))
        b("<Control-plus>", lambda e: self.zoom_by(1.25))
        b("<Control-equal>", lambda e: self.zoom_by(1.25))
        b("<Control-minus>", lambda e: self.zoom_by(1 / 1.25))
        b("<Control-Key-0>", lambda e: self.fit_page())
        b("<Control-Key-1>", lambda e: self.fit_width())
        b("<Control-r>", lambda e: self.rotate())
        b("<F3>", lambda e: self.next_match())
        b("<Shift-F3>", lambda e: self.prev_match())

    # ------------------------------------------------------------------ #
    # 환경설정
    # ------------------------------------------------------------------ #
    def _open_settings(self):
        win = tk.Toplevel(self)
        win.title("환경설정")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        win.iconbitmap(_icon_path("icon.ico")) if os.path.exists(_icon_path("icon.ico")) else None

        body = ttk.Frame(win, padding=14)
        body.pack(fill="both", expand=True)

        vc = tk.IntVar(value=int(self.settings.get("view_cols", 1)))
        vu = tk.StringVar(value="연속" if self.settings.get("view_continuous") else "페이지")
        sf = tk.StringVar(value=self.settings.get("start_fit", "width"))
        zp = tk.IntVar(value=int(self.settings.get("zoom_pct", 100)))
        au = tk.BooleanVar(value=bool(self.settings.get("auto_update", True)))

        row = 0
        ttk.Label(body, text="기본 보기 방식").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=(0, 4))
        row += 1
        for n in COLS_CHOICES:
            ttk.Radiobutton(body, text=_cols_label(n), value=n, variable=vc).grid(
                row=row, column=0, sticky="w", padx=(18, 0))
            row += 1
        nrow = ttk.Frame(body)
        nrow.grid(row=row, column=0, sticky="w", padx=(18, 0), pady=(6, 0))
        ttk.Spinbox(nrow, from_=1, to=MAX_COLS, width=6,
                    textvariable=vc).pack(side="left")
        ttk.Label(nrow, text="쪽씩 (직접 입력)").pack(side="left", padx=4)
        row += 1

        ttk.Label(body, text="").grid(row=row, column=0)
        row += 1
        ttk.Label(body, text="기본 보기 단위").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=(0, 4))
        row += 1
        for text, val in (("페이지 (한 화면씩)", "페이지"), ("연속 (스크롤)", "연속")):
            ttk.Radiobutton(body, text=text, value=val, variable=vu).grid(
                row=row, column=0, sticky="w", padx=(18, 0))
            row += 1

        ttk.Label(body, text="").grid(row=row, column=0)
        row += 1
        ttk.Label(body, text="시작 배율").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=(0, 4))
        row += 1
        for text, val in (("폭 맞춤", "width"), ("쪽 맞춤", "page"), ("지정 배율", "zoom")):
            ttk.Radiobutton(body, text=text, value=val, variable=sf).grid(
                row=row, column=0, sticky="w", padx=(18, 0))
            row += 1
        row += 1
        spinrow = ttk.Frame(body)
        spinrow.grid(row=row, column=0, sticky="w", padx=(18, 0), pady=(4, 0))
        ttk.Spinbox(spinrow, from_=10, to=800, increment=10, width=6,
                    textvariable=zp).pack(side="left")
        ttk.Label(spinrow, text="%  (파일 열 때만 적용)").pack(side="left", padx=4)

        row += 2
        ttk.Separator(body, orient="horizontal").grid(row=row, column=0, sticky="ew", pady=(14, 8))
        row += 1
        ttk.Label(body, text="파일 연결").grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Button(body, text="PDF 기본 프로그램으로 설정",
                   command=self._make_default_app).grid(
            row=row, column=0, sticky="w", padx=(18, 0), pady=(6, 0))

        row += 1
        ttk.Separator(body, orient="horizontal").grid(row=row, column=0, sticky="ew", pady=(14, 8))
        row += 1
        ttk.Checkbutton(body, text="자동 업데이트 (시작 시 새 버전 무음 설치)",
                        variable=au).grid(row=row, column=0, sticky="w")

        btns = ttk.Frame(body)
        btns.grid(row=row + 1, column=0, pady=(16, 0), sticky="e")

        def on_save():
            try:
                z = int(zp.get())
            except ValueError:
                z = 100
            try:
                cols = int(vc.get())
            except (ValueError, tk.TclError):
                cols = self.cols
            cols = max(1, min(MAX_COLS, cols))
            self.settings.update(
                view_cols=cols,
                view_continuous=(vu.get() == "연속"),
                start_fit=sf.get(),
                zoom_pct=max(10, min(800, z)),
                auto_update=bool(au.get()),
            )
            ok = _save_settings(self.settings)
            self.set_view(cols=cols, continuous=(vu.get() == "연속"))
            self._flash_status("설정 저장 완료." if ok else "설정 저장 실패.")
            win.destroy()

        def on_default():
            vc.set(DEFAULT_SETTINGS["view_cols"])
            vu.set("연속" if DEFAULT_SETTINGS["view_continuous"] else "페이지")
            sf.set(DEFAULT_SETTINGS["start_fit"])
            zp.set(DEFAULT_SETTINGS["zoom_pct"])
            au.set(bool(DEFAULT_SETTINGS["auto_update"]))

        ttk.Button(btns, text="기본값", command=on_default).pack(side="left", padx=4)
        ttk.Button(btns, text="취소", command=win.destroy).pack(side="left", padx=4)
        ttk.Button(btns, text="저장", command=on_save).pack(side="left", padx=4)

        win.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - win.winfo_reqwidth()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - win.winfo_reqheight()) // 2
        win.geometry(f"+{max(0, x)}+{max(0, y)}")
        win.focus_set()

    def _make_default_app(self):
        ok, msg = set_default_pdf_app()
        if not ok:
            messagebox.showwarning("기본 프로그램 설정", msg)
            return
        if messagebox.askyesno("기본 프로그램 설정",
                               msg + "\n\nWindows '기본 앱' 설정을 열까요?"):
            open_default_apps_settings()
        self._flash_status("PDF 기본 프로그램 등록 완료.")

    # ------------------------------------------------------------------ #
    # 파일 열기
    # ------------------------------------------------------------------ #
    def on_open(self):
        p = filedialog.askopenfilename(filetypes=PDF_TYPES)
        if p:
            self.open_file(p)

    def on_drop(self, event):
        try:
            paths = list(self.tk.splitlist(event.data))
        except Exception:
            paths = [event.data]
        for p in paths:
            if p.lower().endswith(".pdf"):
                self.open_file(p)
                break
        return event.action

    def open_file(self, path):
        pw = None
        for _ in range(3):
            try:
                self.pdf = pdfium.PdfDocument(path, password=pw)
                break
            except pdfium.PdfiumError as exc:
                if "password" in str(exc).lower():
                    pw = simpledialog.askstring("암호", "PDF 암호:", show="*")
                    if pw is None:
                        return
                else:
                    messagebox.showerror("열기 실패", str(exc))
                    return
        else:
            messagebox.showerror("열기 실패", "암호가 올바르지 않습니다.")
            return

        self.path = path
        self.index = 0
        self.rotation = 0
        self._matches, self._matches_by_page, self.match_pos = [], {}, 0
        self.search_info.set("0/0")
        self.update_idletasks()
        self._apply_start_fit()
        self.title(f"PDF 뷰어 - {os.path.basename(path)}")

    # ------------------------------------------------------------------ #
    # 레이아웃 / 렌더
    # ------------------------------------------------------------------ #
    def _page_points(self, i):
        w, h = self.pdf[i].get_size()
        if self.rotation % 180 == 90:
            w, h = h, w
        return w, h

    def _page_px(self, i):
        w, h = self._page_points(i)
        return w * self.zoom, h * self.zoom

    def _page_offset(self, i):
        if i not in self._layout:
            return 0.0, 0.0
        x, y, w, h = self._layout[i]
        return x + self._cont_offx, y + self._cont_offy

    # ---- 행(row) 단위 레이아웃 ---------------------------------------- #
    def _row_count(self):
        return (len(self.pdf) + self.cols - 1) // self.cols

    def _row_pages(self, r):
        start = r * self.cols
        return list(range(start, min(start + self.cols, len(self.pdf))))

    def _layout_row(self, pages, y_top, out):
        """한 행의 페이지들을 out[page]=(x, y, w, h)에 배치. (row_w, row_h) 반환."""
        dims = [(p, *self._page_px(p)) for p in pages]
        row_h = max((h for _p, _w, h in dims), default=0.0)
        x = GAP
        for p, w, h in dims:
            out[p] = (x, y_top + (row_h - h) / 2, w, h)
            x += w + GAP
        return x, row_h  # x == 행 전체 폭(양끝 GAP 포함)

    def _clear_placed(self):
        for item in self._placed.values():
            self.canvas.delete(item)
        self._placed.clear()
        self._photos.clear()

    def _place_pages(self, pages):
        for p in pages:
            x, y = self._page_offset(p)
            pil = self.pdf[p].render(scale=self.zoom, rotation=self.rotation).to_pil()
            photo = ImageTk.PhotoImage(pil)
            self._photos[p] = photo
            self._placed[p] = self.canvas.create_image(x, y, anchor="nw", image=photo)

    def render(self):
        if not self.pdf:
            return
        if self.continuous:
            self._render_continuous(full=True)
        else:
            self._render_page()

    # ---- 페이지 단위(한 화면씩) --------------------------------------- #
    def _render_page(self):
        self.canvas.delete("all")
        self._clear_placed()

        self.index = (self.index // self.cols) * self.cols  # 현재 행의 첫 페이지
        pages = self._row_pages(self.index // self.cols)

        dims = {p: self._page_px(p) for p in pages}
        row_h = max((h for _w, h in dims.values()), default=0.0)
        spread_w = sum(w for w, _h in dims.values()) + GAP * (len(pages) + 1)
        spread_h = row_h + 2 * GAP

        vp_w = max(1, self.canvas.winfo_width())
        vp_h = max(1, self.canvas.winfo_height())
        if vp_w > spread_w:
            x0 = (vp_w - spread_w) / 2  # 창이 더 넓으면 가로 가운데
            region_w = vp_w
        else:
            x0 = 0.0
            region_w = spread_w
        if vp_h > spread_h:
            y0 = (vp_h - spread_h) / 2  # 창이 더 높으면 세로 가운데
            region_h = vp_h
        else:
            y0 = 0.0
            region_h = spread_h
        self._content_w = region_w
        self._total_h = region_h
        self._cont_offx = 0.0
        self._cont_offy = 0.0

        # 현재 행만 배치
        layout = {}
        x = x0 + GAP
        for p in pages:
            w, h = dims[p]
            layout[p] = (x, y0 + GAP + (row_h - h) / 2, w, h)
            x += w + GAP
        self._layout = layout

        self._place_pages(pages)
        self.canvas.configure(scrollregion=(0, 0, region_w, region_h))
        self._draw_highlights()
        self._update_status(spread_w, row_h)

    # ---- 연속 스크롤 -------------------------------------------------- #
    def _build_layout(self):
        layout = {}
        y = GAP
        maxw = 0.0
        for r in range(self._row_count()):
            row_w, row_h = self._layout_row(self._row_pages(r), y, layout)
            maxw = max(maxw, row_w)
            y += row_h + GAP
        self._layout = layout
        self._natural_w = maxw
        self._natural_h = y
        self._cont_offx = 0.0
        self._cont_offy = 0.0

    def _render_continuous(self, full=False):
        if full:
            self.canvas.delete("all")
            self._clear_placed()
            self._build_layout()
        self._ensure_continuous()

    def _ensure_continuous(self):
        if not self.continuous or not self.pdf:
            return
        vp_w = max(1, self.canvas.winfo_width())
        vp_h = max(1, self.canvas.winfo_height())
        # 창보다 내용이 작으면 창 크기에 맞추고 가운데 정렬
        region_w = max(vp_w, self._natural_w)
        region_h = max(vp_h, self._natural_h)
        self._content_w = region_w
        self._total_h = region_h
        self._cont_offx = (region_w - self._natural_w) / 2
        self._cont_offy = (region_h - self._natural_h) / 2

        top = self.canvas.canvasy(0)
        bot = top + vp_h
        buf = vp_h  # 위/아래 한 화면 분량 미리 렌더

        visible = [i for i, (x, ly, w, ph) in self._layout.items()
                   if ly + self._cont_offy + ph >= top - buf
                   and ly + self._cont_offy <= bot + buf]
        vset = set(visible)

        for i in list(self._placed):
            if i not in vset:
                self.canvas.delete(self._placed.pop(i))
                self._photos.pop(i, None)

        self._place_pages([i for i in visible if i not in self._placed])

        self.canvas.configure(scrollregion=(0, 0, region_w, region_h))
        self._draw_highlights()
        self._update_status(None, None)

    def _on_scrollbar(self, *args):
        self.canvas.yview(*args)
        self._ensure_continuous()

    def _scroll_units(self, units):
        if not self.continuous:
            if units < 0:
                self.prev_page()
            elif units > 0:
                self.next_page()
            return
        self.canvas.yview_scroll(units, "units")
        self._ensure_continuous()

    def on_configure(self, _event=None):
        if not self.pdf:
            return
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(60, self._refresh_after_resize)

    def _refresh_after_resize(self):
        self._resize_job = None
        if not self.pdf:
            return
        if self._fit:
            self._refit()  # 폭/쪽 맞춤 중 → 배율도 같이 재계산
        elif self.continuous:
            self._render_continuous(full=True)
        else:
            self.render()  # 페이지 단위 → 가운데 정렬 재계산

    def _update_status(self, w, h):
        if not self.pdf:
            return
        total = len(self.pdf)
        self.total_var.set(f"/ {total}")
        self.page_var.set(str(self.index + 1))
        self.zoom_var.set(f"{int(round(self.zoom * 100))}%")

    def _title_base(self):
        name = os.path.basename(self.path or "")
        return f"PDF 뷰어 - {name}" if name else "PDF 뷰어"

    def _flash_status(self, text):
        base = self._title_base()
        self.title(f"{base}    {text}" if text else base)
        job = getattr(self, "_status_job", None)
        if job is not None:
            try:
                self.after_cancel(job)
            except Exception:
                pass
        self._status_job = self.after(2500, lambda: self.title(base))

    def _apply_start_fit(self):
        sm = self.settings if isinstance(self.settings, dict) else DEFAULT_SETTINGS
        fit = sm.get("start_fit", "width")
        if fit == "page":
            self._fit = "page"
            self.fit_page()
        elif fit == "zoom":
            self._fit = None
            self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, sm.get("zoom_pct", 100) / 100.0))
            self.render()
        else:  # width
            self._fit = "width"
            self.fit_width()

    def _refit(self):
        if self._fit == "width":
            self.fit_width()
        elif self._fit == "page":
            self.fit_page()

    # ------------------------------------------------------------------ #
    # 무음 자동 업데이트
    # ------------------------------------------------------------------ #
    def _update_worker(self):
        try:
            info = fetch_update_info()
        except Exception:
            return
        if not info:
            return
        if _version_tuple(info.get("version")) <= _version_tuple(__version__):
            return
        try:
            path = download_update(info)
        except Exception:
            path = None
        if not path:
            return
        try:
            self.after(0, lambda: self._run_update(path, info.get("version", "")))
        except Exception:
            pass

    def _run_update(self, path, version):
        if not launch_silent_update(path, _app_exe()):
            return
        self._flash_status(f"새 버전 {version} 설치를 위해 잠시 후 다시 시작합니다...")
        self.after(1200, self.destroy)

    # ------------------------------------------------------------------ #
    # 페이지 이동 / 줌 / 회전
    # ------------------------------------------------------------------ #
    def prev_page(self):
        self.goto(self.index - self.cols)

    def next_page(self):
        self.goto(self.index + self.cols)

    def goto(self, i):
        if not self.pdf:
            return
        self.index = max(0, min(len(self.pdf) - 1, i))
        if self.continuous:
            self._scroll_to_page(self.index)
        elif self._fit:
            # 폭/쪽 맞춤 중 → 페이지 방향(세로/가로)이 달라도 맞춤 유지
            self._refit()
        else:
            self.render()

    def on_page_jump(self, _event=None):
        try:
            self.goto(int(self.page_var.get()) - 1)
        except ValueError:
            pass

    def zoom_by(self, factor):
        if not self.pdf:
            return
        self._fit = None  # 수동 확대 → 창 크기 추적 해제
        self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, self.zoom * factor))
        self.render()

    def _row_fit_zoom(self, mode):
        """현재 행(현재 페이지가 속한 행) 기준 맞춤 배율."""
        pages = self._row_pages(self.index // self.cols)
        pts = [self._page_points(p) for p in pages] or [(1.0, 1.0)]
        total_w = sum(w for w, _h in pts) or 1.0
        max_h = max((h for _w, h in pts), default=1.0) or 1.0
        n = len(pages)
        cw = max(1, self.canvas.winfo_width() - 6)
        ch = max(1, self.canvas.winfo_height() - 6)
        z_w = (cw - GAP * (n + 1)) / total_w
        if mode == "width":
            # 여러 쪽 보기는 가로 맞춤이라도 세로로 넘치면 자동 축소
            return z_w if self.cols == 1 else min(z_w, (ch - 2 * GAP) / max_h)
        z_h = (ch - 2 * GAP) / max_h
        return min(z_w, z_h)

    def fit_width(self):
        if not self.pdf:
            return
        self._fit = "width"
        self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, self._row_fit_zoom("width")))
        self.render()

    def fit_page(self):
        if not self.pdf:
            return
        self._fit = "page"
        self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, self._row_fit_zoom("page")))
        self.render()

    def rotate(self):
        if not self.pdf:
            return
        self.rotation = (self.rotation + 90) % 360
        if self._fit:
            self._refit()
        else:
            self.render()

    def _on_cols_n(self, _event=None):
        try:
            n = int(float(self.cols_n_var.get()))
        except (ValueError, TypeError):
            n = self.cols
        self.set_view(cols=n)

    def set_view(self, cols=None, continuous=None):
        if cols is not None:
            self.cols = max(1, min(MAX_COLS, int(cols)))
        if continuous is not None:
            self.continuous = bool(continuous)
        self._sync_view_controls()
        if self.pdf:
            self.render()
            if self.continuous:
                self._scroll_to_page(self.index)
        else:
            self._update_status(None, None)

    def _sync_view_controls(self):
        if hasattr(self, "cols_n_var"):
            self.cols_n_var.set(str(self.cols))
        if hasattr(self, "unit_var"):
            self.unit_var.set("연속" if self.continuous else "페이지")

    # ------------------------------------------------------------------ #
    # 좌표 변환 / 하이라이트
    # ------------------------------------------------------------------ #
    def _map_rect_px(self, l, b, r, t, pw, ph, ox, oy):
        rot = self.rotation % 360
        us, vs = [], []
        for x, y in ((l, b), (l, t), (r, b), (r, t)):
            if rot == 0:
                u, v = x, ph - y
            elif rot == 90:
                u, v = y, x
            elif rot == 180:
                u, v = pw - x, y
            else:
                u, v = ph - y, pw - x
            us.append(u)
            vs.append(v)
        z = self.zoom
        return (min(us) * z + ox, min(vs) * z + oy, max(us) * z + ox, max(vs) * z + oy)

    def _draw_highlights(self):
        self.canvas.delete("hl")
        if not self._matches_by_page or not self.pdf:
            return
        for i, items in self._matches_by_page.items():
            if i not in self._placed:
                continue
            pw, ph = self.pdf[i].get_size()
            ox, oy = self._page_offset(i)
            for gi, box in items:
                x0, y0, x1, y1 = self._map_rect_px(*box, pw, ph, ox, oy)
                current = gi == self.match_pos
                self.canvas.create_rectangle(
                    x0, y0, x1, y1,
                    outline="#e05a00" if current else "#c9a227",
                    width=2 if current else 1,
                    fill="#ff8c00" if current else "#ffe066",
                    stipple="gray50",
                    tags="hl",
                )

    def _scroll_to_page(self, i):
        self._ensure_continuous()
        if i not in self._layout:
            return
        x, y, w, ph = self._layout[i]
        frac = (y + self._cont_offy - GAP) / max(1.0, self._total_h)
        self.canvas.yview_moveto(max(0.0, min(1.0, frac)))
        self._ensure_continuous()

    # ------------------------------------------------------------------ #
    # 검색
    # ------------------------------------------------------------------ #
    def do_search(self):
        text = self.search_var.get().strip()
        self._matches, self._matches_by_page, self.match_pos = [], {}, 0
        if text and self.pdf:
            for i in range(len(self.pdf)):
                tp = self.pdf[i].get_textpage()
                searcher = tp.search(text, match_case=False)
                while True:
                    res = searcher.get_next()
                    if not res:
                        break
                    start, count = res
                    box = self._union_charbox(tp, start, count)
                    if box:
                        self._matches.append((i, box))
                tp.close()
        for gi, (i, box) in enumerate(self._matches):
            self._matches_by_page.setdefault(i, []).append((gi, box))

        if self._matches:
            self.match_pos = 0
            self._goto_match()
        else:
            self.search_info.set("0/0")
            self._draw_highlights()

    def _union_charbox(self, tp, start, count):
        x0 = y0 = 1e9
        x1 = y1 = -1e9
        for k in range(start, start + count):
            try:
                b = tp.get_charbox(k)
            except Exception:
                continue
            if not b:
                continue
            x0 = min(x0, b[0]); y0 = min(y0, b[1])
            x1 = max(x1, b[2]); y1 = max(y1, b[3])
        if x1 < 0:
            return None
        return (x0, y0, x1, y1)

    def next_match(self):
        if not self._matches:
            return
        self.match_pos = (self.match_pos + 1) % len(self._matches)
        self._goto_match()

    def prev_match(self):
        if not self._matches:
            return
        self.match_pos = (self.match_pos - 1) % len(self._matches)
        self._goto_match()

    def _goto_match(self):
        if not self._matches:
            return
        i, box = self._matches[self.match_pos]
        self.index = i
        self.search_info.set(f"{self.match_pos + 1}/{len(self._matches)}")
        if self.continuous:
            self._ensure_continuous()
        else:
            self.render()  # 매치가 있는 행 표시
        self._draw_highlights()
        self._scroll_to_box(i, box)

    def _scroll_to_box(self, i, box):
        if self.continuous:
            self._ensure_continuous()
        pw, ph = self.pdf[i].get_size()
        ox, oy = self._page_offset(i)
        _, y0, _, y1 = self._map_rect_px(*box, pw, ph, ox, oy)
        cy = (y0 + y1) / 2
        vp = max(1, self.canvas.winfo_height())
        total = max(1.0, self._total_h)
        frac = (cy - vp / 3) / total
        self.canvas.yview_moveto(max(0.0, min(1.0, frac)))
        if self.continuous:
            self._ensure_continuous()

    # ------------------------------------------------------------------ #
    # 스크롤 / 팬
    # ------------------------------------------------------------------ #
    def on_wheel(self, event):
        if event.state & 0x0004:  # Ctrl → 줌
            self.zoom_by(1.15 if event.delta > 0 else 1 / 1.15)
        elif event.state & 0x0001:  # Shift → 가로 스크롤
            self.canvas.xview_scroll(int(-event.delta / 120), "units")
        else:
            self._scroll_units(int(-event.delta / 120))

    def start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def do_pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("-")]
    PdfViewer(argv[0] if argv else None).mainloop()


if __name__ == "__main__":
    main()
