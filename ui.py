from __future__ import annotations
#hello world !
import json
import math
import os
import platform
import random
import sys
import threading
import time
from pathlib import Path

from PyQt6.QtCore import (
    QPointF, QRectF, Qt, QTimer, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QIcon, QImage, QKeySequence,
    QPainter, QPainterPath, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QSizePolicy, QTextEdit,
    QVBoxLayout, QWidget,
)


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"

_DEFAULT_W, _DEFAULT_H = 1060, 700
_MIN_W,     _MIN_H     = 820, 560
_OS = platform.system()


# ─── PALETTE — Cream / White / Grey ──────────────────────────────────────────
class C:
    BG        = "#f5f4f0"   # warm cream canvas
    PANEL     = "#eeede8"   # panel base (slightly deeper cream)
    PANEL2    = "#e6e5df"   # cards / inset panels
    BORDER    = "#d0cfc8"   # subtle border
    BORDER_B  = "#b0afa8"   # active border
    BORDER_A  = "#c4c3bb"

    # Text
    INK       = "#1a1918"   # near-black main text
    INK_MED   = "#474747"   # medium text
    INK_DIM   = "#707070"   # dim / placeholder

    # Animation — bold dark on white
    DARK1     = "#1a1918"   # primary dark (rings, arcs)
    DARK2     = "#3a3835"   # secondary dark
    DARK3     = "#5a5855"   # tertiary

    # Accent / state
    RED       = "#b03030"   # muted/error
    RED_BG    = "#f5ecea"
    ACTIVE    = "#1a1918"   # active state = darkest ink
    WAVE_ON   = "#2a2825"   # waveform active
    WAVE_OFF  = "#c0bfb8"   # waveform idle

    # Shadows/borders on dark elements
    SHADOW    = "#0000001a"


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c


# ─── Window Icon (drawn programmatically) ────────────────────────────────────
def _make_icon(size: int = 64) -> QIcon:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    cx = cy = size / 2
    r = size / 2 - 2

    # white circle bg
    p.setBrush(QBrush(QColor("#ffffff")))
    p.setPen(QPen(QColor("#1a1918"), 2))
    p.drawEllipse(QRectF(2, 2, size-4, size-4))

    # bold J letter
    p.setFont(QFont("Courier New", int(size * 0.40), QFont.Weight.Black))
    p.setPen(QPen(QColor("#1a1918")))
    p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "J")

    # thin outer ring
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor("#1a1918"), 1.5))
    p.drawEllipse(QRectF(1, 1, size-2, size-2))

    p.end()
    return QIcon(QPixmap.fromImage(img))


# ─── HUD Canvas ──────────────────────────────────────────────────────────────
class HudCanvas(QWidget):
    def __init__(self, face_path: str, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.muted    = False
        self.speaking = False
        self.state    = "INITIALISING"

        self._tick       = 0
        self._scale      = 1.0
        self._tgt_scale  = 1.0
        self._halo       = 55.0
        self._tgt_halo   = 55.0
        self._last_t     = time.time()
        self._scan       = 0.0
        self._scan2      = 180.0
        self._rings      = [0.0, 120.0, 240.0]
        self._pulses: list[float] = [0.0, 50.0, 100.0]
        self._blink      = True
        self._blink_tick = 0
        self._particles: list[list[float]] = []
        self._face_px: QPixmap | None = None
        self._load_face(face_path)

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def _load_face(self, path: str):
        try:
            from PIL import Image, ImageDraw
            import io
            img = Image.open(path).convert("RGBA")
            sz  = min(img.size)
            img = img.resize((sz, sz), Image.LANCZOS)
            mk  = Image.new("L", (sz, sz), 0)
            ImageDraw.Draw(mk).ellipse((2, 2, sz-2, sz-2), fill=255)
            img.putalpha(mk)
            buf = io.BytesIO(); img.save(buf, format="PNG")
            px = QPixmap(); px.loadFromData(buf.getvalue())
            self._face_px = px
        except Exception:
            self._face_px = None

    def _step(self):
        self._tick += 1
        now = time.time()
        if now - self._last_t > (0.12 if self.speaking else 0.5):
            if self.speaking:
                self._tgt_scale = random.uniform(1.04, 1.10)
                self._tgt_halo  = random.uniform(130, 175)
            elif self.muted:
                self._tgt_scale = random.uniform(0.998, 1.002)
                self._tgt_halo  = random.uniform(10, 22)
            else:
                self._tgt_scale = random.uniform(1.001, 1.007)
                self._tgt_halo  = random.uniform(44, 62)
            self._last_t = now

        sp = 0.32 if self.speaking else 0.14
        self._scale += (self._tgt_scale - self._scale) * sp
        self._halo  += (self._tgt_halo  - self._halo)  * sp

        speeds = [1.1, -0.75, 1.7] if self.speaking else [0.45, -0.28, 0.75]
        for i, spd in enumerate(speeds):
            self._rings[i] = (self._rings[i] + spd) % 360

        self._scan  = (self._scan  + (2.4 if self.speaking else 1.0)) % 360
        self._scan2 = (self._scan2 + (-1.6 if self.speaking else -0.6)) % 360

        fw  = min(self.width(), self.height())
        lim = fw * 0.74
        spd = 3.5 if self.speaking else 1.6
        self._pulses = [r + spd for r in self._pulses if r + spd < lim]
        if len(self._pulses) < 3 and random.random() < (0.06 if self.speaking else 0.022):
            self._pulses.append(0.0)

        if self.speaking and random.random() < 0.22:
            cx, cy = self.width()/2, self.height()/2
            ang = random.uniform(0, 2*math.pi)
            r_s = fw * 0.28
            self._particles.append([
                cx + math.cos(ang)*r_s, cy + math.sin(ang)*r_s,
                math.cos(ang)*random.uniform(0.8, 2.0),
                math.sin(ang)*random.uniform(0.8, 2.0)-0.3, 1.0,
            ])
        self._particles = [
            [p[0]+p[2], p[1]+p[3], p[2]*0.97, p[3]*0.97, p[4]-0.030]
            for p in self._particles if p[4] > 0
        ]

        self._blink_tick += 1
        if self._blink_tick >= 38:
            self._blink = not self._blink
            self._blink_tick = 0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # cream background
        p.fillRect(self.rect(), qcol(C.BG))

        W, H = self.width(), self.height()
        cx, cy = W/2, H/2
        fw = min(W, H)

        # subtle dot grid — very faint
        p.setPen(QPen(qcol(C.BORDER, 80), 1))
        for x in range(0, W, 48):
            for y in range(0, H, 48):
                p.drawPoint(x, y)

        r_face  = fw * 0.31
        # dark ink or red for muted
        pri_col = C.RED if self.muted else C.DARK1
        sec_col = C.RED if self.muted else C.DARK2
        ter_col = C.RED if self.muted else C.DARK3

        # halo — concentric faint rings outward (dark on white = bold)
        for i in range(9):
            r   = r_face * (1.75 - i * 0.07)
            frc = 1.0 - i/9
            # stronger alpha than before — dark on white is naturally bold
            a   = max(0, min(255, int(self._halo * 0.10 * frc)))
            p.setPen(QPen(qcol(pri_col, a), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx-r, cy-r, r*2, r*2))

        # pulse rings — bold expanding circles
        for pr in self._pulses:
            a = max(0, int(220 * (1.0 - pr/(fw*0.74))))
            p.setPen(QPen(qcol(pri_col, a), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx-pr, cy-pr, pr*2, pr*2))

        # spinning arc rings — thick, dark, bold
        for idx, (r_frac, w_r, arc_l, gap) in enumerate(
            [(0.48, 3, 100, 80), (0.40, 2, 68, 58), (0.32, 1.5, 48, 42)]
        ):
            ring_r = fw * r_frac
            base   = self._rings[idx]
            a_val  = max(0, min(255, int(self._halo * (1.1 - idx*0.22))))
            col    = [pri_col, sec_col, ter_col][idx]
            p.setPen(QPen(qcol(col, a_val), w_r))
            p.setBrush(Qt.BrushStyle.NoBrush)
            angle = base
            rect  = QRectF(cx-ring_r, cy-ring_r, ring_r*2, ring_r*2)
            while angle < base + 360:
                p.drawArc(rect, int(angle*16), int(arc_l*16))
                angle += arc_l + gap

        # scanner arcs
        sr = fw * 0.50
        sa = min(255, int(self._halo * 1.6))
        ex = 65 if self.speaking else 38
        p.setPen(QPen(qcol(pri_col, sa), 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        srect = QRectF(cx-sr, cy-sr, sr*2, sr*2)
        p.drawArc(srect, int(self._scan*16),  int(ex*16))
        p.setPen(QPen(qcol(sec_col, sa//2), 1.5))
        p.drawArc(srect, int(self._scan2*16), int(ex*16))

        # tick marks
        t_out, t_in = fw*0.497, fw*0.474
        p.setPen(QPen(qcol(C.DARK3, 100), 1))
        for deg in range(0, 360, 10):
            rad = math.radians(deg)
            inn = t_in if deg % 30 == 0 else t_in + 6
            p.drawLine(
                QPointF(cx + t_out*math.cos(rad), cy - t_out*math.sin(rad)),
                QPointF(cx + inn *math.cos(rad), cy - inn *math.sin(rad)),
            )

        # crosshair — thin, dark
        ch_r, gap_h = fw*0.51, fw*0.16
        p.setPen(QPen(qcol(C.DARK2, int(self._halo*0.55)), 1))
        p.drawLine(QPointF(cx-ch_r, cy), QPointF(cx-gap_h, cy))
        p.drawLine(QPointF(cx+gap_h, cy), QPointF(cx+ch_r, cy))
        p.drawLine(QPointF(cx, cy-ch_r), QPointF(cx, cy-gap_h))
        p.drawLine(QPointF(cx, cy+gap_h), QPointF(cx, cy+ch_r))

        # corner brackets — sharp dark
        bl = 22
        hl, hr = cx - fw//2, cx + fw//2
        ht, hb = cy - fw//2, cy + fw//2
        p.setPen(QPen(qcol(C.DARK1, 200), 2))
        for bx, by, dx, dy in [(hl,ht,1,1),(hr,ht,-1,1),(hl,hb,1,-1),(hr,hb,-1,-1)]:
            p.drawLine(QPointF(bx, by), QPointF(bx+dx*bl, by))
            p.drawLine(QPointF(bx, by), QPointF(bx, by+dy*bl))

        # face / orb
        if self._face_px:
            fsz    = int(fw * 0.62 * self._scale)
            scaled = self._face_px.scaled(
                fsz, fsz,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            p.drawPixmap(int(cx-fsz/2), int(cy-fsz/2), scaled)
        else:
            # dark orb on cream background
            orb_r = int(fw * 0.26 * self._scale)
            for i in range(8, 0, -1):
                r2  = int(orb_r * i / 8)
                frc = i / 8
                if self.muted:
                    base_c = QColor("#b03030")
                else:
                    base_c = QColor("#1a1918")
                base_c.setAlpha(max(0, min(255, int(self._halo * 1.1 * frc))))
                p.setBrush(QBrush(base_c)); p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(cx-r2, cy-r2, r2*2, r2*2))
            # J.A.R.V.I.S text on orb
            p.setPen(QPen(qcol("#f5f4f0", min(255, int(self._halo*2.0))), 1))
            p.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
            p.drawText(QRectF(cx-80, cy-12, 160, 24),
                       Qt.AlignmentFlag.AlignCenter, "J.A.R.V.I.S")

        # particles
        for pt in self._particles:
            a = max(0, min(255, int(pt[4]*255)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qcol(C.DARK1, a)))
            p.drawEllipse(QPointF(pt[0], pt[1]), 2.2, 2.2)

        # status text
        sy = cy + fw * 0.40
        if self.muted:
            txt, col = "⊘  MUTED",       qcol(C.RED)
        elif self.speaking:
            txt, col = "●  SPEAKING",    qcol(C.DARK1)
        elif self.state == "THINKING":
            sym = "◈" if self._blink else "◇"
            txt, col = f"{sym}  THINKING",   qcol(C.INK_MED)
        elif self.state == "PROCESSING":
            sym = "▷" if self._blink else "▶"
            txt, col = f"{sym}  PROCESSING", qcol(C.INK_MED)
        elif self.state == "LISTENING":
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  LISTENING",  qcol(C.DARK2)
        else:
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  {self.state}", qcol(C.INK_MED)

        p.setPen(QPen(col, 1))
        p.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        p.drawText(QRectF(0, sy, W, 26), Qt.AlignmentFlag.AlignCenter, txt)

        # waveform bars — dark on cream
        wy = sy + 30
        N, bw = 36, 8
        wx0 = (W - N*bw) / 2
        for i in range(N):
            if self.muted:
                hgt, cl = 2, qcol(C.RED, 160)
            elif self.speaking:
                hgt = random.randint(3, 18)
                cl  = qcol(C.DARK1) if hgt > 11 else qcol(C.DARK3)
            else:
                hgt = int(3 + 2*math.sin(self._tick*0.09 + i*0.6))
                cl  = qcol(C.WAVE_OFF)
            p.fillRect(QRectF(wx0 + i*bw, wy + 20 - hgt, bw-2, hgt), cl)


# ─── Chat Log ────────────────────────────────────────────────────────────────
class LogWidget(QTextEdit):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Courier New", 9))
        self.setStyleSheet(f"""
            QTextEdit {{
                background: {C.PANEL2};
                color: {C.INK};
                border: 1px solid {C.BORDER};
                border-radius: 6px;
                padding: 8px;
                selection-background-color: {C.BORDER_B};
            }}
            QScrollBar:vertical {{
                background: {C.PANEL};
                width: 5px; border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_B};
                border-radius: 2px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        self._queue: list[str] = []
        self._typing = False
        self._text   = ""
        self._pos    = 0
        self._tag    = "sys"
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._sig.connect(self._enqueue)

    def append_log(self, text: str):
        self._sig.emit(text)

    def _enqueue(self, text: str):
        self._queue.append(text)
        if not self._typing:
            self._next()

    def _next(self):
        if not self._queue:
            self._typing = False; return
        self._typing = True
        self._text   = self._queue.pop(0)
        self._pos    = 0
        tl = self._text.lower()
        if   tl.startswith("you:"):    self._tag = "you"
        elif tl.startswith("jarvis:"): self._tag = "ai"
        elif tl.startswith("file:"):   self._tag = "file"
        elif "err" in tl:              self._tag = "err"
        else:                          self._tag = "sys"
        self._tmr.start(6)

    def _step(self):
        if self._pos < len(self._text):
            ch  = self._text[self._pos]
            cur = self.textCursor()
            fmt = cur.charFormat()
            col = {
                "you":  qcol(C.INK),
                "ai":   qcol(C.DARK2),
                "err":  qcol(C.RED),
                "file": qcol(C.INK_MED),
                "sys":  qcol(C.INK_DIM),
            }.get(self._tag, qcol(C.INK))
            fmt.setForeground(QBrush(col))
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText(ch, fmt)
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            self._pos += 1
        else:
            self._tmr.stop()
            cur = self.textCursor()
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText("\n")
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            QTimer.singleShot(20, self._next)


# ─── File Drop Zone ───────────────────────────────────────────────────────────
_FILE_ICONS = {
    "image": "🖼", "video": "🎬", "audio": "🎵", "pdf": "📄",
    "word":  "📝", "excel": "📊", "code":  "💻", "archive": "📦",
    "pptx":  "📊", "text":  "📃", "data":  "🔧", "unknown": "📎",
}
_EXT_TO_CAT = {
    **dict.fromkeys(["jpg","jpeg","png","gif","webp","bmp","tiff","svg","ico"], "image"),
    **dict.fromkeys(["mp4","avi","mov","mkv","wmv","flv","webm","m4v"],         "video"),
    **dict.fromkeys(["mp3","wav","ogg","m4a","aac","flac","wma","opus"],        "audio"),
    **dict.fromkeys(["pdf"],                                                     "pdf"),
    **dict.fromkeys(["doc","docx"],                                              "word"),
    **dict.fromkeys(["xls","xlsx","ods"],                                        "excel"),
    **dict.fromkeys(["ppt","pptx"],                                              "pptx"),
    **dict.fromkeys(["py","js","ts","jsx","tsx","html","css","java","c","cpp",
                     "cs","go","rs","rb","php","swift","kt","sh","sql","lua"],   "code"),
    **dict.fromkeys(["zip","rar","tar","gz","7z","bz2","xz"],                   "archive"),
    **dict.fromkeys(["txt","md","rst","log"],                                    "text"),
    **dict.fromkeys(["csv","tsv","json","xml"],                                  "data"),
}

def _file_category(path: Path) -> str:
    return _EXT_TO_CAT.get(path.suffix.lower().lstrip("."), "unknown")

def _fmt_size(size: int) -> str:
    if   size < 1024:    return f"{size} B"
    elif size < 1024**2: return f"{size/1024:.1f} KB"
    elif size < 1024**3: return f"{size/1024**2:.1f} MB"
    else:                return f"{size/1024**3:.1f} GB"


class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(72)
        self._current_file: str | None = None
        self._hovering   = False
        self._drag_over  = False
        self._dash_off   = 0.0
        tmr = QTimer(self); tmr.timeout.connect(self._anim); tmr.start(40)
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0)
        self._canvas = _DropCanvas(self); lay.addWidget(self._canvas)

    def _anim(self):
        self._dash_off = (self._dash_off + 0.7) % 20
        self._canvas.update()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction(); self._drag_over = True; self._canvas.update()

    def dragLeaveEvent(self, e):
        self._drag_over = False; self._canvas.update()

    def dropEvent(self, e):
        self._drag_over = False
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file(): self._set_file(path)
        self._canvas.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self._browse()

    def enterEvent(self, e):  self._hovering = True;  self._canvas.update()
    def leaveEvent(self, e):  self._hovering = False; self._canvas.update()
    def current_file(self) -> str | None: return self._current_file
    def clear_file(self):     self._current_file = None; self._canvas.update()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select file", str(Path.home()), "All Files (*.*)")
        if path: self._set_file(path)

    def _set_file(self, path: str):
        self._current_file = path; self._canvas.update(); self.file_selected.emit(path)


class _DropCanvas(QWidget):
    def __init__(self, zone: FileDropZone):
        super().__init__(zone); self._z = zone

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z = self._z; W, H = self.width(), self.height()
        pad = 4
        rect = QRectF(pad, pad, W-pad*2, H-pad*2)

        bg = qcol("#e8e7e1" if z._drag_over else ("#eeedea" if z._hovering else C.PANEL2))
        p.setBrush(QBrush(bg)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   bc = qcol(C.DARK2, 200)
        elif z._drag_over:    bc = qcol(C.DARK1, 220)
        elif z._hovering:     bc = qcol(C.BORDER_B, 200)
        else:                 bc = qcol(C.BORDER, 160)

        pen = QPen(bc, 1, Qt.PenStyle.DashLine); pen.setDashOffset(z._dash_off)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 6, 6)

        cx, cy = W/2, H/2

        if z._current_file:
            path = Path(z._current_file)
            icon = _FILE_ICONS.get(_file_category(path), "📎")
            size_str = _fmt_size(path.stat().st_size)
            name = path.name if len(path.name) <= 34 else path.name[:31]+"..."
            p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            p.setPen(QPen(qcol(C.INK), 1))
            p.drawText(QRectF(12, cy-12, W-50, 16),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{icon}  {name}")
            p.setFont(QFont("Courier New", 7))
            p.setPen(QPen(qcol(C.INK_DIM), 1))
            p.drawText(QRectF(12, cy+4, W-50, 14),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, size_str)
            p.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
            p.setPen(QPen(qcol(C.RED, 160), 1))
            p.drawText(QRectF(W-34, 0, 28, H), Qt.AlignmentFlag.AlignCenter, "✕")
        elif z._drag_over:
            p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            p.setPen(QPen(qcol(C.DARK1), 1))
            p.drawText(QRectF(0,0,W,H), Qt.AlignmentFlag.AlignCenter, "↓  Release to load")
        else:
            p.setPen(QPen(qcol(C.INK_DIM if not z._hovering else C.INK_MED), 1))
            p.setFont(QFont("Courier New", 8))
            p.drawText(QRectF(0, cy-10, W, 20), Qt.AlignmentFlag.AlignCenter,
                       "↑  Drop file  ·  Click to browse")

    def mousePressEvent(self, e):
        z = self._z
        if z._current_file and e.pos().x() > self.width()-34: z.clear_file()
        else: z.mousePressEvent(e)


# ─── Setup Overlay ────────────────────────────────────────────────────────────
class SetupOverlay(QWidget):
    done = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: rgba(245, 244, 240, 248);
                border: 1px solid {C.BORDER_B};
                border-radius: 8px;
            }}
        """)

        detected = {"darwin": "mac", "windows": "windows"}.get(_OS.lower(), "linux")
        self._sel_os = detected

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 22, 30, 22)
        layout.setSpacing(8)

        def _lbl(txt, sz=9, bold=False, color=C.INK, align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt); w.setAlignment(align)
            w.setFont(QFont("Courier New", sz, QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl("◈  INITIALISATION REQUIRED", 13, True))
        layout.addWidget(_lbl("Configure J.A.R.V.I.S. before first boot.", 9, color=C.INK_MED))
        layout.addSpacing(6)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep)
        layout.addSpacing(4)

        layout.addWidget(_lbl("GEMINI API KEY", 8, color=C.INK_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza…")
        self._key_input.setFont(QFont("Courier New", 10))
        self._key_input.setFixedHeight(34)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background: {C.PANEL2}; color: {C.INK};
                border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 10px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.DARK2}; }}
        """)
        layout.addWidget(self._key_input)
        layout.addSpacing(12)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep2)
        layout.addSpacing(4)

        layout.addWidget(_lbl("OPERATING SYSTEM", 8, color=C.INK_DIM, align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected: {det_name}", 8, color=C.INK_MED,
                               align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(6)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows","⊞  Windows"),("mac","  macOS"),("linux","⬡  Linux")]:
            btn = QPushButton(label)
            btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel(detected)
        layout.addSpacing(12)

        init_btn = QPushButton("▸  INITIALISE SYSTEMS")
        init_btn.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        init_btn.setFixedHeight(36)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.DARK1}; color: {C.BG};
                border: none; border-radius: 4px; letter-spacing: 1px;
            }}
            QPushButton:hover {{ background: {C.DARK2}; }}
        """)
        init_btn.clicked.connect(self._submit)
        layout.addWidget(init_btn)

    def _sel(self, key: str):
        self._sel_os = key
        for k, btn in self._os_btns.items():
            if k == key:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.DARK1}; color: {C.BG};
                        border: none; border-radius: 4px; font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PANEL2}; color: {C.INK_MED};
                        border: 1px solid {C.BORDER}; border-radius: 4px;
                    }}
                    QPushButton:hover {{ color: {C.INK}; border: 1px solid {C.BORDER_B}; }}
                """)

    def _submit(self):
        key = self._key_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(
                self._key_input.styleSheet() + f" QLineEdit {{ border: 1px solid {C.RED}; }}")
            return
        self.done.emit(key, self._sel_os)


# ─── Main Window ──────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    _log_sig   = pyqtSignal(str)
    _state_sig = pyqtSignal(str)

    def __init__(self, face_path: str):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S ")
        self.setWindowIcon(_make_icon(64))
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width()-_DEFAULT_W)//2, (screen.height()-_DEFAULT_H)//2)

        self.on_text_command  = None
        self._muted           = False
        self._current_file: str | None = None

        central = QWidget()
        central.setStyleSheet(f"background: {C.BG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.hud = HudCanvas(face_path)
        self.hud.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body.addWidget(self.hud, stretch=5)
        body.addWidget(self._build_right_panel(), stretch=0)

        root.addLayout(body, stretch=1)
        root.addWidget(self._build_footer())

        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()

        self._log_sig.connect(self._log.append_log)
        self._state_sig.connect(self._apply_state)

        self._overlay: SetupOverlay | None = None
        self._ready = self._check_config()
        if not self._ready:
            self._show_setup()

        from PyQt6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("F4"),  self).activated.connect(self._toggle_mute)
        QShortcut(QKeySequence("F11"), self).activated.connect(self._toggle_fullscreen)

    def _toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._overlay and self._overlay.isVisible():
            ow, oh = 460, 390
            cw = self.centralWidget()
            self._overlay.setGeometry((cw.width()-ow)//2, (cw.height()-oh)//2, ow, oh)

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(54)
        w.setStyleSheet(
            f"background: {C.PANEL};"
            f"border-bottom: 1px solid {C.BORDER_B};"
        )
        lay = QHBoxLayout(w)
        lay.setContentsMargins(20, 0, 20, 0)

        def _badge(txt, color=C.INK_DIM):
            l = QLabel(txt); l.setFont(QFont("Courier New", 7))
            l.setStyleSheet(f"color: {color}; background: transparent;"); return l

        lay.addWidget(_badge("", C.INK_DIM))
        lay.addStretch()

        mid = QVBoxLayout(); mid.setSpacing(1)
        title = QLabel("JARVIS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Courier New", 16, QFont.Weight.Black))
        title.setStyleSheet(f"color: {C.INK}; background: transparent; letter-spacing: 5px;")
        mid.addWidget(title)
        sub = QLabel("For you, Sir, always.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(QFont("Courier New", 7))
        sub.setStyleSheet(f"color: {C.INK_DIM}; background: transparent;")
        mid.addWidget(sub)
        lay.addLayout(mid)
        lay.addStretch()

        right_col = QVBoxLayout(); right_col.setSpacing(2)
        self._clock_lbl = QLabel("00:00:00")
        self._clock_lbl.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        self._clock_lbl.setStyleSheet(f"color: {C.INK}; background: transparent;")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._clock_lbl)
        self._date_lbl = QLabel("")
        self._date_lbl.setFont(QFont("Courier New", 7))
        self._date_lbl.setStyleSheet(f"color: {C.INK_DIM}; background: transparent;")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._date_lbl)
        lay.addLayout(right_col)
        return w

    def _tick_clock(self):
        self._clock_lbl.setText(time.strftime("%H:%M:%S"))
        self._date_lbl.setText(time.strftime("%a %d %b %Y"))

    # ── Right Panel ───────────────────────────────────────────────────────────
    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(310)
        w.setStyleSheet(f"background: {C.PANEL}; border-left: 1px solid {C.BORDER_B};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(9)

        def _sec(txt):
            l = QLabel(f"▸ {txt}")
            l.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            l.setStyleSheet(f"color: {C.INK_DIM}; background: transparent;")
            return l

        lay.addWidget(_sec("ACTIVITY LOG"))
        self._log = LogWidget()
        lay.addWidget(self._log, stretch=1)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};"); lay.addWidget(sep)

        lay.addWidget(_sec("FILE UPLOAD"))
        self._drop_zone = FileDropZone()
        self._drop_zone.file_selected.connect(self._on_file_selected)
        lay.addWidget(self._drop_zone)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER};"); lay.addWidget(sep2)

        lay.addWidget(_sec("COMMAND INPUT"))
        lay.addLayout(self._build_input_row())

        # Mute button
        self._mute_btn = QPushButton("●  MICROPHONE ACTIVE")
        self._mute_btn.setFixedHeight(34)
        self._mute_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_btn.clicked.connect(self._toggle_mute)
        self._style_mute_btn()
        lay.addWidget(self._mute_btn)
        return w

    def _build_input_row(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(6)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a command…")
        self._input.setFont(QFont("Courier New", 9))
        self._input.setFixedHeight(34)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: {C.PANEL2}; color: {C.INK};
                border: 1px solid {C.BORDER}; border-radius: 4px; padding: 3px 10px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.DARK2}; }}
        """)
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input)

        send = QPushButton("▸")
        send.setFixedSize(34, 34)
        send.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setStyleSheet(f"""
            QPushButton {{
                background: {C.DARK1}; color: {C.BG};
                border: none; border-radius: 4px;
            }}
            QPushButton:hover {{ background: {C.DARK2}; }}
        """)
        send.clicked.connect(self._send)
        row.addWidget(send)
        return row

    # ── Footer ────────────────────────────────────────────────────────────────
    def _build_footer(self) -> QWidget:
        w = QWidget(); w.setFixedHeight(20)
        w.setStyleSheet(f"background: {C.PANEL}; border-top: 1px solid {C.BORDER};")
        lay = QHBoxLayout(w); lay.setContentsMargins(14, 0, 14, 0)

        def _fl(txt, color=C.INK_DIM):
            l = QLabel(txt); l.setFont(QFont("Courier New", 7))
            l.setStyleSheet(f"color: {color}; background: transparent;"); return l

        lay.addWidget(_fl("[F4] Mute  ·  [F11] Fullscreen"))
        lay.addStretch()
        lay.addWidget(_fl(""))
        lay.addStretch()
        lay.addWidget(_fl("© Sadi", C.INK_MED))
        return w

    # ── Handlers ──────────────────────────────────────────────────────────────
    def _on_file_selected(self, path: str):
        self._current_file = path
        p   = Path(path)
        size = _fmt_size(p.stat().st_size)
        self._log.append_log(f"FILE: {p.name} ({size}) loaded")
        if self.on_text_command:
            msg = (f"[FILE_UPLOADED] path={path} | name={p.name} | "
                   f"type={p.suffix.lstrip('.')} | size={size} | "
                   f"Briefly tell the user you can see the file '{p.name}' "
                   f"({size}) has been uploaded and ask what they'd like to do with it.")
            threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()

    def _toggle_mute(self):
        self._muted = not self._muted
        self.hud.muted = self._muted
        self._style_mute_btn()
        if self._muted:
            self._apply_state("MUTED")
            self._log.append_log("SYS: Microphone muted.")
        else:
            self._apply_state("LISTENING")
            self._log.append_log("SYS: Microphone active.")

    def _style_mute_btn(self):
        if self._muted:
            self._mute_btn.setText("⊘  MICROPHONE MUTED")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C.RED_BG}; color: {C.RED};
                    border: 1px solid {C.RED}; border-radius: 4px; letter-spacing: 1px;
                }}
                QPushButton:hover {{ background: #f0e0de; }}
            """)
        else:
            self._mute_btn.setText("●  MICROPHONE ACTIVE")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C.PANEL2}; color: {C.INK_MED};
                    border: 1px solid {C.BORDER}; border-radius: 4px; letter-spacing: 1px;
                }}
                QPushButton:hover {{
                    background: {C.PANEL}; border: 1px solid {C.BORDER_B}; color: {C.INK};
                }}
            """)

    def _send(self):
        txt = self._input.text().strip()
        if not txt: return
        self._input.clear()
        self._log.append_log(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt,), daemon=True).start()

    def _apply_state(self, state: str):
        self.hud.state    = state
        self.hud.speaking = (state == "SPEAKING")

    def _check_config(self) -> bool:
        if not API_FILE.exists(): return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return bool(d.get("gemini_api_key")) and bool(d.get("os_system"))
        except Exception: return False

    def _show_setup(self):
        ov = SetupOverlay(self.centralWidget())
        cw = self.centralWidget()
        ow, oh = 460, 390
        ov.setGeometry((cw.width()-ow)//2, (cw.height()-oh)//2, ow, oh)
        ov.done.connect(self._on_setup_done)
        ov.show(); self._overlay = ov

    def _on_setup_done(self, key: str, os_name: str):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        API_FILE.write_text(json.dumps({"gemini_api_key": key, "os_system": os_name}, indent=4),
                            encoding="utf-8")
        self._ready = True
        if self._overlay:
            self._overlay.hide(); self._overlay = None
        self._apply_state("LISTENING")
        self._log.append_log(f"SYS: Initialised. OS={os_name.upper()}. JARVIS online.")


# ─── Public API ───────────────────────────────────────────────────────────────
class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app
    def mainloop(self): self._app.exec()
    def protocol(self, *_): pass


class JarvisUI:
    def __init__(self, face_path: str, size=None):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = MainWindow(face_path)
        self._win.show()
        self.root = _RootShim(self._app)

    @property
    def muted(self) -> bool: return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted: self._win._toggle_mute()

    @property
    def current_file(self) -> str | None:
        return self._win._drop_zone.current_file()

    @property
    def on_text_command(self): return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb): self._win.on_text_command = cb

    def set_state(self, state: str): self._win._state_sig.emit(state)
    def write_log(self, text: str):  self._win._log_sig.emit(text)

    def wait_for_api_key(self):
        while not self._win._ready: time.sleep(0.1)

    def start_speaking(self): self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted: self.set_state("LISTENING")
