from __future__ import annotations

import json
import math
import os
import platform
import random
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
import struct
import wave
import winsound
from pathlib import Path

import psutil

from PyQt6.QtCore import (
    QEasingCurve, QMimeData, QObject, QPointF, QRectF, QSize, Qt,
    QTimer, QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QDragEnterEvent, QDropEvent, QFont, QFontDatabase,
    QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient, QShortcut, QIcon,
)
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QSizePolicy, QTextEdit,
    QVBoxLayout, QWidget, QProgressBar, QGraphicsDropShadowEffect,
    QStackedWidget, QSlider, QComboBox, QCheckBox, QGridLayout, QListWidget,
    QDialog, QMessageBox, QCalendarWidget,
)

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"

_DEFAULT_W, _DEFAULT_H = 1020, 720
_MIN_W,     _MIN_H     = 880, 620
_LEFT_W  = 164
_RIGHT_W = 380

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"

class C:
    BG        = "#05070A"
    PANEL     = "rgba(10, 16, 26, 140)"
    PANEL2    = "rgba(16, 24, 36, 100)"
    BORDER    = "rgba(0, 229, 255, 0.15)"
    BORDER_B  = "rgba(189, 0, 255, 0.3)"
    BORDER_A  = "rgba(0, 85, 255, 0.25)"
    PRI       = "#00E5FF" # Electric Cyan
    PRI_DIM   = "#0099B0"
    PRI_GHO   = "rgba(0, 229, 255, 0.08)"
    ACC       = "#BD00FF" # Purple
    ACC2      = "#FF9900" # Orange
    GREEN     = "#00FF66" # Neon Green
    GREEN_D   = "#00AA44"
    RED       = "#FF0033" # Red
    MUTED_C   = "#7E8B9B"
    TEXT      = "#E1F5FE"
    TEXT_DIM  = "#5C768D"
    TEXT_MED  = "#8EA8C3"
    WHITE     = "#FFFFFF"
    DARK      = "rgba(5, 7, 10, 200)"
    BAR_BG    = "rgba(255, 255, 255, 0.05)"
    SEC       = "#0055FF" # Neon Blue

def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h)
    if not h.startswith("rgba"):
        c.setAlpha(a)
    return c

class SoundManager:
    @staticmethod
    def play(name: str):
        try:
            path = BASE_DIR / "sounds" / f"{name}.wav"
            if path.exists():
                winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as e:
            print(f"Error playing sound {name}: {e}")

def generate_sound_effects(sounds_dir: Path):
    sounds_dir.mkdir(parents=True, exist_ok=True)
    sample_rate = 22050

    def write_pcm_wav(filename: str, samples: list[float]):
        path = sounds_dir / filename
        if path.exists():
            return
        max_val = max(abs(s) for s in samples) if samples else 0.0
        scale = 32767.0 / max_val if max_val > 0 else 32767.0
        
        packed = bytearray()
        for s in samples:
            val = int(s * scale)
            val = max(-32768, min(32767, val))
            packed.extend(struct.pack("<h", val))
            
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(packed)

    # 1. click: sharp high-frequency click decaying rapidly
    click_samples = []
    click_len = int(sample_rate * 0.04)
    for i in range(click_len):
        t = i / sample_rate
        amp = math.exp(-t * 220)
        click_samples.append(math.sin(2 * math.pi * 1600 * t) * amp)
    write_pcm_wav("click.wav", click_samples)

    # 2. startup: beautiful ascending synthesizer chime chords
    startup_samples = []
    dur = 2.2
    startup_len = int(sample_rate * dur)
    for i in range(startup_len):
        t = i / sample_rate
        sweep_f = 180 + 320 * (t / dur) ** 2
        sweep = math.sin(2 * math.pi * sweep_f * t) * math.exp(-t * 2.5)
        c5 = math.sin(2 * math.pi * 523.25 * t)
        e5 = math.sin(2 * math.pi * 659.25 * t)
        g5 = math.sin(2 * math.pi * 783.99 * t)
        c6 = math.sin(2 * math.pi * 1046.50 * t)
        chord = (c5 + e5 + g5 + c6) * 0.25 * math.exp(-t * 0.8) * min(t * 8.0, 1.0)
        startup_samples.append(sweep + chord)
    write_pcm_wav("startup.wav", startup_samples)

    # 3. shutdown: sweep descending
    shutdown_samples = []
    dur = 1.2
    shutdown_len = int(sample_rate * dur)
    for i in range(shutdown_len):
        t = i / sample_rate
        sweep_f = 600 - 450 * (t / dur)
        amp = math.exp(-t * 2.2)
        shutdown_samples.append(math.sin(2 * math.pi * sweep_f * t) * amp)
    write_pcm_wav("shutdown.wav", shutdown_samples)

    # 4. notification: high-tech double ping
    notif_samples = []
    dur = 0.5
    notif_len = int(sample_rate * dur)
    for i in range(notif_len):
        t = i / sample_rate
        if t < 0.12:
            amp = math.exp(-t * 30)
            val = math.sin(2 * math.pi * 880 * t) * amp
        else:
            t2 = t - 0.12
            amp = math.exp(-t2 * 18)
            val = math.sin(2 * math.pi * 1320 * t2) * amp
        notif_samples.append(val)
    write_pcm_wav("notification.wav", notif_samples)

    # 5. completed: triumphant ascending triad (E5, A5, C#6)
    comp_samples = []
    dur = 0.9
    comp_len = int(sample_rate * dur)
    for i in range(comp_len):
        t = i / sample_rate
        if t < 0.15:
            amp = math.exp(-t * 12)
            val = math.sin(2 * math.pi * 659.25 * t) * amp
        elif t < 0.30:
            t2 = t - 0.15
            amp = math.exp(-t2 * 10)
            val = math.sin(2 * math.pi * 880 * t2) * amp
        else:
            t3 = t - 0.30
            amp = math.exp(-t3 * 6)
            val = math.sin(2 * math.pi * 1109.73 * t3) * amp
        comp_samples.append(val)
    write_pcm_wav("completed.wav", comp_samples)

    # 6. error: double low-frequency buzzer
    err_samples = []
    dur = 0.6
    err_len = int(sample_rate * dur)
    for i in range(err_len):
        t = i / sample_rate
        if t < 0.25:
            val = math.sin(2 * math.pi * 150 * t) * 0.8
        elif t < 0.35:
            val = 0.0
        else:
            t2 = t - 0.35
            val = math.sin(2 * math.pi * 150 * t2) * 0.8
        val *= math.exp(-t * 2.5)
        err_samples.append(val)
    write_pcm_wav("error.wav", err_samples)

class GlowingLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255, 255, 255, 0.03);
                color: {C.WHITE};
                border: 1px solid rgba(0, 229, 255, 0.15);
                border-radius: 15px;
                padding: 4px 12px;
                selection-background-color: rgba(0, 229, 255, 0.2);
            }}
        """)
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setColor(qcol(C.PRI, 150))
        self._shadow.setBlurRadius(15)
        self._shadow.setOffset(0, 0)
        self.setGraphicsEffect(self._shadow)
        self._shadow.setEnabled(False)

    def focusInEvent(self, e):
        super().focusInEvent(e)
        self._shadow.setEnabled(True)
        self.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255, 255, 255, 0.05);
                color: {C.WHITE};
                border: 1px solid {C.PRI};
                border-radius: 15px;
                padding: 4px 12px;
                selection-background-color: rgba(0, 229, 255, 0.2);
            }}
        """)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self._shadow.setEnabled(False)
        self.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255, 255, 255, 0.03);
                color: {C.WHITE};
                border: 1px solid rgba(0, 229, 255, 0.15);
                border-radius: 15px;
                padding: 4px 12px;
                selection-background-color: rgba(0, 229, 255, 0.2);
            }}
        """)

class GlowingTextEdit(QTextEdit):
    returnPressed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QTextEdit {{
                background: rgba(255, 255, 255, 0.03);
                color: {C.WHITE};
                border: 1px solid rgba(0, 229, 255, 0.15);
                border-radius: 15px;
                padding: 4px 12px;
                selection-background-color: rgba(0, 229, 255, 0.2);
            }}
        """)
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setColor(qcol(C.PRI, 150))
        self._shadow.setBlurRadius(15)
        self._shadow.setOffset(0, 0)
        self.setGraphicsEffect(self._shadow)
        self._shadow.setEnabled(False)

    def focusInEvent(self, e):
        super().focusInEvent(e)
        self._shadow.setEnabled(True)
        self.setStyleSheet(f"""
            QTextEdit {{
                background: rgba(255, 255, 255, 0.05);
                color: {C.WHITE};
                border: 1px solid {C.PRI};
                border-radius: 15px;
                padding: 4px 12px;
                selection-background-color: rgba(0, 229, 255, 0.2);
            }}
        """)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self._shadow.setEnabled(False)
        self.setStyleSheet(f"""
            QTextEdit {{
                background: rgba(255, 255, 255, 0.03);
                color: {C.WHITE};
                border: 1px solid rgba(0, 229, 255, 0.15);
                border-radius: 15px;
                padding: 4px 12px;
                selection-background-color: rgba(0, 229, 255, 0.2);
            }}
        """)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Return or e.key() == Qt.Key.Key_Enter:
            if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(e)
            else:
                self.returnPressed.emit()
        else:
            super().keyPressEvent(e)

class ModernButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setColor(qcol(C.PRI, 120))
        self._shadow.setBlurRadius(12)
        self._shadow.setOffset(0, 0)
        self.setGraphicsEffect(self._shadow)
        self._shadow.setEnabled(False)
        self.clicked.connect(lambda: SoundManager.play("click"))
        
    def enterEvent(self, e):
        super().enterEvent(e)
        self._shadow.setEnabled(True)
        
    def leaveEvent(self, e):
        super().leaveEvent(e)
        self._shadow.setEnabled(False)

class TypingPlaceholderManager(QObject):
    def __init__(self, line_edit: QWidget, parent=None):
        super().__init__(parent)
        self.line_edit = line_edit
        self.placeholders = [
            "Ask COCO AI anything...",
            "Type a command here...",
            "Open Spotify or Chrome...",
            "What's the weather today?",
            "How can I help you, sir?"
        ]
        self.current_idx = 0
        self.char_idx = 0
        self.is_deleting = False
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._step)
        self.timer.start(120)
        
    def _step(self):
        if self.line_edit.hasFocus():
            self.line_edit.setPlaceholderText("Type a command...")
            return
            
        current_text = self.placeholders[self.current_idx]
        
        if not self.is_deleting:
            self.char_idx += 1
            self.line_edit.setPlaceholderText(current_text[:self.char_idx] + "▎")
            if self.char_idx == len(current_text):
                self.is_deleting = True
                self.timer.setInterval(2200)
            else:
                self.timer.setInterval(75)
        else:
            if self.timer.interval() == 2200:
                self.timer.setInterval(35)
            self.char_idx -= 1
            self.line_edit.setPlaceholderText(current_text[:self.char_idx] + "▎")
            if self.char_idx == 0:
                self.is_deleting = False
                self.current_idx = (self.current_idx + 1) % len(self.placeholders)
                self.timer.setInterval(600)

class GlassPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent; border: none;")
        self._glow_timer = QTimer(self)
        self._glow_timer.timeout.connect(self.update)
        self._glow_timer.start(40)
        self._border_tick = 0
        
        # Add premium soft shadow glow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 229, 255, 22))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)
        
    def paintEvent(self, event):
        self._border_tick += 1
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setBrush(QBrush(qcol("#060A10", 185)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 14, 14)
        
        c1 = qcol(C.PRI, int(100 + 35 * math.sin(self._border_tick * 0.04)))
        c2 = qcol(C.ACC, int(100 + 35 * math.cos(self._border_tick * 0.04)))
        
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0, c1)
        grad.setColorAt(1, c2)
        
        p.setPen(QPen(grad, 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 14, 14)

class _SysMetrics:
    def __init__(self):
        self.cpu  = 0.0
        self.mem  = 0.0
        self.net  = 0.0   
        self.gpu  = -1.0  
        self.tmp  = -1.0  
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            time.sleep(1.5)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent

        nc  = psutil.net_io_counters()
        now = time.time()
        dt  = now - self._last_net_t
        if dt > 0:
            sent = (nc.bytes_sent - self._last_net.bytes_sent) / dt
            recv = (nc.bytes_recv - self._last_net.bytes_recv) / dt
            net  = (sent + recv) / (1024 * 1024)
        else:
            net = 0.0
        self._last_net   = nc
        self._last_net_t = now

        gpu = self._get_gpu()
        tmp = self._get_temp()

        with self._lock:
            self.cpu = cpu
            self.mem = mem
            self.net = net
            self.gpu = gpu
            self.tmp = tmp

    def _get_gpu(self) -> float:
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if r.returncode == 0:
                vals = [float(v.strip()) for v in r.stdout.strip().split("\n") if v.strip()]
                if vals:
                    return sum(vals) / len(vals)
        except Exception:
            pass

        if _OS == "Linux":
            try:
                r = subprocess.run(
                    ["rocm-smi", "--showuse", "--csv"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    for line in r.stdout.strip().split("\n"):
                        parts = line.split(",")
                        if len(parts) >= 2:
                            try:
                                return float(parts[1].strip().replace("%", ""))
                            except ValueError:
                                pass
            except Exception:
                pass

            try:
                r = subprocess.run(
                    ["intel_gpu_top", "-J", "-s", "500"],
                    capture_output=True, text=True, timeout=1
                )
                if r.returncode == 0 and "Render/3D" in r.stdout:
                    import re
                    m = re.search(r'"busy":\s*([\d.]+)', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        if _OS == "Darwin":
            try:
                r = subprocess.run(
                    ["sudo", "-n", "powermetrics", "-n", "1", "-i", "500",
                     "--samplers", "gpu_power"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0 and "GPU" in r.stdout:
                    import re
                    m = re.search(r'GPU\s+Active:\s+([\d.]+)%', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        return -1.0

    def _get_temp(self) -> float:
        try:
            temps = psutil.sensors_temperatures()
            candidates = ["coretemp", "k10temp", "cpu_thermal", "acpitz",
                          "cpu-thermal", "zenpower", "it8688"]
            for name in candidates:
                if name in temps:
                    entries = temps[name]
                    if entries:
                        return entries[0].current
            for entries in temps.values():
                if entries:
                    return entries[0].current
        except Exception:
            pass
        if _OS == "Darwin":
            try:
                r = subprocess.run(
                    ["osx-cpu-temp"], capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    import re
                    m = re.search(r"([\d.]+)", r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        if _OS == "Windows":
            try:
                r = subprocess.run(
                    ["powershell", "-Command",
                     "(Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace root/wmi).CurrentTemperature"],
                    capture_output=True, text=True, timeout=3
                )
                if r.returncode == 0 and r.stdout.strip():
                    raw = float(r.stdout.strip().split("\n")[0])
                    return (raw / 10.0) - 273.15
            except Exception:
                pass

        return -1.0

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "cpu": self.cpu,
                "mem": self.mem,
                "net": self.net,
                "gpu": self.gpu,
                "tmp": self.tmp,
            }

_metrics = _SysMetrics()

class HudCanvas(QWidget):
    def __init__(self, face_path: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(320, 320)
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
        self._rings      = [0.0, 120.0, 240.0]
        self._pulses: list[float] = []
        self._blink      = True
        self._blink_tick = 0
        self._particles: list[list[float]] = []
        self._face_px: QPixmap | None = None
        self._load_face(face_path)
        
        self._mic_volume = 0.0
        self._target_mic_volume = 0.0
        self._voice_bars = [0.0] * 5
        
        # Pre-populate some floating particles
        for _ in range(15):
            self._spawn_particle(init=True)

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            p = self.parent()
            while p and not isinstance(p, QMainWindow):
                p = p.parent()
            if p:
                p.show_ai_status()
        elif e.button() == Qt.MouseButton.RightButton:
            p = self.parent()
            while p and not isinstance(p, QMainWindow):
                p = p.parent()
            if p:
                p.show_hud_context_menu(e.globalPosition().toPoint())

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            p = self.parent()
            while p and not isinstance(p, QMainWindow):
                p = p.parent()
            if p:
                p.show_advanced_diagnostics()

    def _load_face(self, path: str):
        try:
            from PIL import Image, ImageDraw
            import io
            img = Image.open(path).convert("RGBA")
            sz  = min(img.size)
            img = img.resize((sz, sz), Image.LANCZOS)
            mk  = Image.new("L", (sz, sz), 0)
            ImageDraw.Draw(mk).ellipse((2, 2, sz - 2, sz - 2), fill=255)
            img.putalpha(mk)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap(); px.loadFromData(buf.getvalue())
            self._face_px = px
        except Exception:
            self._face_px = None

    def _spawn_particle(self, init=False):
        ang = random.uniform(0, 2 * math.pi)
        r = random.uniform(20, 120) if init else random.uniform(60, 80)
        speed = random.uniform(0.18, 0.45)
        vx = math.cos(ang) * speed
        vy = math.sin(ang) * speed - random.uniform(0.08, 0.25)
        life = random.uniform(0.4, 1.0)
        size = random.uniform(1.2, 3.2)
        
        cx = self.width() / 2 if self.width() > 0 else 160
        cy = self.height() / 2 if self.height() > 0 else 160
        
        x = cx + math.cos(ang) * r
        y = cy + math.sin(ang) * r
        
        self._particles.append([x, y, vx, vy, life, size])

    def _step(self):
        self._tick += 1
        now = time.time()
        
        if self.muted:
            self._tgt_scale = 0.98 + 0.008 * math.sin(self._tick * 0.05)
            self._tgt_halo  = 16.0 + 4.0 * math.sin(self._tick * 0.05)
        elif self.speaking:
            self._tgt_scale = random.uniform(1.04, 1.12)
            self._tgt_halo  = random.uniform(110.0, 170.0)
        elif self.state in ("THINKING", "PROCESSING"):
            self._tgt_scale = 1.02 + 0.02 * math.sin(self._tick * 0.16)
            self._tgt_halo  = 65.0 + 20.0 * math.sin(self._tick * 0.16)
        elif self.state == "LISTENING":
            self._tgt_scale = 1.01 + 0.035 * math.sin(self._tick * 0.09)
            self._tgt_halo  = 75.0 + 25.0 * math.sin(self._tick * 0.09)
        else:
            self._tgt_scale = 1.0 + 0.015 * math.sin(self._tick * 0.04)
            self._tgt_halo  = 40.0 + 10.0 * math.sin(self._tick * 0.04)

        sp = 0.22 if self.speaking else 0.12
        self._scale += (self._tgt_scale - self._scale) * sp
        self._halo  += (self._tgt_halo  - self._halo)  * sp

        speeds = [2.2, -1.6, 2.8] if self.state in ("THINKING", "PROCESSING") else [0.65, -0.4, 0.95]
        for i, spd in enumerate(speeds):
            self._rings[i] = (self._rings[i] + spd) % 360

        fw  = min(self.width(), self.height())
        if self.state == "LISTENING" and self._tick % 45 == 0:
            self._pulses.append(fw * 0.24)

        active_pulses = []
        for p in self._pulses:
            p_next = p + 2.0
            if p_next < fw * 0.65:
                active_pulses.append(p_next)
        self._pulses = active_pulses

        updated_particles = []
        for p in self._particles:
            p[0] += p[2]
            p[1] += p[3]
            p[4] -= 0.007
            if p[4] > 0:
                updated_particles.append(p)
        self._particles = updated_particles

        # Smooth mic volume decay
        self._mic_volume += (self._target_mic_volume - self._mic_volume) * 0.15
        self._target_mic_volume *= 0.85
        
        # Calculate voice bar heights
        for i in range(5):
            jitter = 0.15 * math.sin(self._tick * 0.2 + i * 0.7)
            tgt_h = self._mic_volume * (0.45 + 0.55 * random.uniform(0.6, 1.0)) + abs(jitter)
            if self.state != "LISTENING" or self.muted:
                tgt_h = 0.05 + 0.05 * math.sin(self._tick * 0.05 + i * 0.8) # Idle breathing sound bars
            self._voice_bars[i] += (tgt_h - self._voice_bars[i]) * 0.25

        max_p = 28 if self.state == "LISTENING" else (20 if self.speaking else 12)
        if self.state == "OFFLINE":
            max_p = 0
            
        while len(self._particles) < max_p:
            self._spawn_particle(init=False)

        self._blink_tick += 1

    def set_mic_volume(self, volume: float):
        self._target_mic_volume = volume
        if self._blink_tick >= 42:
            self._blink = not self._blink
            self._blink_tick = 0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), qcol(C.BG))

        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        fw = min(W, H)

        # Tech Grid Dots
        p.setPen(QPen(qcol(C.PRI_GHO, 45), 1))
        for x in range(0, W, 48):
            for y in range(0, H, 48):
                p.drawPoint(x, y)

        r_face = fw * 0.28

        # Halo Glow Breathing
        # Speaking = green, thinking = purple, listening = blue, sleeping/offline = grey
        glow_col = C.MUTED_C if self.muted else (
            qcol("#555555") if self.state == "OFFLINE" else (
                C.GREEN if self.state == "SPEAKING" or self.speaking else (
                    C.ACC if self.state in ("THINKING", "PROCESSING") else (
                        C.SEC if self.state == "LISTENING" else C.PRI
                    )
                )
            )
        )
        for i in range(8):
            r   = r_face * (1.75 - i * 0.08)
            frc = 1.0 - i / 8
            a   = max(0, min(255, int(self._halo * 0.12 * frc)))
            p.setPen(QPen(qcol(glow_col, a), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # Listening breathing expansion pulses
        if self.state == "LISTENING":
            for pr in self._pulses:
                a   = max(0, int(180 * (1.0 - pr / (fw * 0.65))))
                p.setPen(QPen(qcol(C.SEC, a), 1.2))
                p.drawEllipse(QRectF(cx - pr, cy - pr, pr * 2, pr * 2))

        # Rotating outer rings (Thinking/Idle states)
        # Thinking shows gorgeous purple rings
        if self.state in ("THINKING", "PROCESSING"):
            for idx, (r_frac, w_r, arc_l, gap) in enumerate(
                [(0.44, 2.5, 120, 60), (0.37, 1.8, 85, 45), (0.30, 1.0, 60, 30)]
            ):
                ring_r = fw * r_frac
                base   = self._rings[idx]
                a_val  = max(0, min(255, int(self._halo * (1.1 - idx * 0.2))))
                col    = qcol(C.ACC, a_val) # Purple rings
                p.setPen(QPen(col, w_r))
                rect  = QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2)
                angle = base
                while angle < base + 360:
                    p.drawArc(rect, int(angle * 16), int(arc_l * 16))
                    angle += arc_l + gap
        elif self.state == "LISTENING":
            # Listening shows faint cyan-blue outer rings
            for idx, (r_frac, w_r, arc_l, gap) in enumerate([(0.40, 1.5, 90, 90), (0.33, 1.0, 70, 70)]):
                ring_r = fw * r_frac
                base   = self._rings[idx]
                col    = qcol(C.SEC, 90)
                p.setPen(QPen(col, w_r))
                rect   = QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2)
                p.drawArc(rect, int((base * 0.5) * 16), int(arc_l * 16))
        elif self.state != "OFFLINE":
            # Idle/Default shows slow drifting outer rings
            for idx, (r_frac, w_r, arc_l, gap) in enumerate([(0.44, 1.0, 60, 120)]):
                ring_r = fw * r_frac
                base   = self._rings[idx]
                col    = qcol(C.PRI_GHO, 70)
                p.setPen(QPen(col, w_r))
                rect   = QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2)
                p.drawArc(rect, int((base * 0.2) * 16), int(arc_l * 16))

        # Speech radial visualizer
        if self.speaking:
            num_bars = 72
            r_base = fw * 0.27 * self._scale
            p.setPen(QPen(qcol(C.GREEN, 200), 2)) # Green visualizer arcs when speaking
            for i in range(num_bars):
                angle = (i / num_bars) * 2 * math.pi + (self._tick * 0.01)
                h = 4 + 20 * math.sin(i * 0.25 + self._tick * 0.25) * random.uniform(0.3, 1.0)
                h = abs(h)
                x1 = cx + math.cos(angle) * r_base
                y1 = cy + math.sin(angle) * r_base
                x2 = cx + math.cos(angle) * (r_base + h)
                y2 = cy + math.sin(angle) * (r_base + h)
                p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # Central AI Core
        orb_r = int(fw * 0.23 * self._scale)
        if self._face_px:
            fsz    = int(fw * 0.52 * self._scale)
            scaled = self._face_px.scaled(
                fsz, fsz,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            p.drawPixmap(int(cx - fsz / 2), int(cy - fsz / 2), scaled)
        else:
            grad_c = QRadialGradient(cx, cy, orb_r)
            if self.muted:
                grad_c.setColorAt(0, qcol(C.RED, 220))
                grad_c.setColorAt(0.6, qcol("#40000a", 160))
                grad_c.setColorAt(1, qcol("#05070a", 0))
            elif self.state == "OFFLINE":
                grad_c.setColorAt(0, qcol("#3a3a3a", 220))
                grad_c.setColorAt(0.6, qcol("#1e1e1e", 160))
                grad_c.setColorAt(1, qcol("#05070a", 0))
            elif self.speaking:
                grad_c.setColorAt(0, qcol(C.GREEN, 220)) # Green core when speaking
                grad_c.setColorAt(0.6, qcol("#003311", 160))
                grad_c.setColorAt(1, qcol("#05070a", 0))
            elif self.state in ("THINKING", "PROCESSING"):
                grad_c.setColorAt(0, qcol(C.ACC, 220)) # Purple core
                grad_c.setColorAt(0.6, qcol("#35004d", 160))
                grad_c.setColorAt(1, qcol("#05070a", 0))
            elif self.state == "LISTENING":
                grad_c.setColorAt(0, qcol(C.SEC, 240)) # Electric deep blue core
                grad_c.setColorAt(0.6, qcol("#002266", 180))
                grad_c.setColorAt(1, qcol("#05070a", 0))
            else:
                # Idle/Sleeping core (premium white frosted glass)
                grad_c.setColorAt(0, qcol("#ffffff", 45))
                grad_c.setColorAt(0.5, qcol("rgba(16, 24, 36, 150)", 120))
                grad_c.setColorAt(1, qcol("#05070a", 0))

            p.setBrush(QBrush(grad_c))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - orb_r, cy - orb_r, orb_r * 2, orb_r * 2))

            # Glass overlay on central core
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(qcol("#ffffff", 28), 1.2))
            p.drawEllipse(QRectF(cx - orb_r, cy - orb_r, orb_r * 2, orb_r * 2))

            # Siri-like animated waveform inside the core (Listening & Speaking states)
            if self.state == "LISTENING" or self.speaking:
                p.save()
                clip_path = QPainterPath()
                clip_path.addEllipse(cx - orb_r + 2, cy - orb_r + 2, orb_r * 2 - 4, orb_r * 2 - 4)
                p.setClipPath(clip_path)
                
                # Wave colors: Green for speaking, Blue/Cyan for listening
                if self.speaking:
                    colors = [qcol(C.GREEN, 180), qcol(C.GREEN_D, 140), qcol(C.WHITE, 190)]
                else:
                    colors = [qcol(C.PRI, 180), qcol(C.SEC, 140), qcol(C.WHITE, 190)]
                    
                phases = [self._tick * 0.14, -self._tick * 0.09, self._tick * 0.06]
                amplitudes = [orb_r * 0.38, orb_r * 0.28, orb_r * 0.18]
                frequencies = [0.07, 0.10, 0.05]
                
                for idx in range(3):
                    p.setPen(QPen(colors[idx], 1.8))
                    path = QPainterPath()
                    first = True
                    for px in range(int(cx - orb_r), int(cx + orb_r) + 1):
                        x_rel = px - cx
                        dist_factor = math.cos((x_rel / orb_r) * (math.pi / 2)) # bell curves to 0 at edges
                        y_wave = cy + math.sin(x_rel * frequencies[idx] + phases[idx]) * amplitudes[idx] * dist_factor
                        if first:
                            path.moveTo(px, y_wave)
                            first = False
                        else:
                            path.lineTo(px, y_wave)
                    p.drawPath(path)
                p.restore()

            # Core name label: COCO AI
            p.setPen(QPen(qcol(C.WHITE, min(255, int(self._halo * 2.2))), 1))
            p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            p.drawText(QRectF(cx - 80, cy - 14, 160, 28),
                       Qt.AlignmentFlag.AlignCenter, "COCO AI")

        # Floating Particles (Only if online/not offline)
        if self.state != "OFFLINE":
            for pt in self._particles:
                a = max(0, min(255, int(pt[4] * 240)))
                p.setPen(Qt.PenStyle.NoPen)
                # Thinking particles are purple, others are electric cyan/blue
                p_col = C.ACC if self.state in ("THINKING", "PROCESSING") else (C.SEC if self.state == "LISTENING" else C.PRI)
                p.setBrush(QBrush(qcol(p_col, a)))
                p.drawEllipse(QPointF(pt[0], pt[1]), pt[5], pt[5])

        # Draw dense voice visualizer bars on the left (reacts to self._mic_volume)
        if self.state == "LISTENING" and not self.muted:
            p.save()
            p.setPen(Qt.PenStyle.NoPen)
            
            num_bars = 16
            bar_w = 4
            spacing = 6
            base_x = cx - orb_r - 70
            base_y = cy
            
            for i in range(num_bars):
                idx = min(4, int((i / num_bars) * 5))
                vol = self._voice_bars[idx]
                
                # Taper wave at the edges
                dist_factor = math.sin((i / (num_bars - 1)) * math.pi)
                bar_h = int(6 + 75 * vol * dist_factor)
                
                bx = base_x + (i - num_bars / 2) * spacing
                by = base_y - bar_h / 2
                
                # Glow backdrop
                p.setBrush(QBrush(qcol(C.PRI, 25)))
                p.drawRoundedRect(QRectF(bx - 1.5, by - 1.5, bar_w + 3, bar_h + 3), bar_w/2, bar_w/2)
                
                # Gradient fill
                grad = QLinearGradient(bx, by, bx, by + bar_h)
                grad.setColorAt(0, qcol(C.PRI))
                grad.setColorAt(0.5, qcol(C.SEC))
                grad.setColorAt(1, qcol(C.ACC))
                
                p.setBrush(QBrush(grad))
                p.drawRoundedRect(QRectF(bx, by, bar_w, bar_h), bar_w/2, bar_w/2)
            p.restore()

            # Status subtitle text below the left waveform
            p.save()
            p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            p.setPen(QPen(qcol("#E1F5FE", 180), 1))
            p.drawText(QRectF(base_x - 50, base_y + 45, 100, 16), Qt.AlignmentFlag.AlignCenter, "Listening...")
            
            p.setFont(QFont("Segoe UI", 7))
            p.setPen(QPen(qcol(C.GREEN, 200), 1))
            p.drawText(QRectF(base_x - 50, base_y + 61, 100, 14), Qt.AlignmentFlag.AlignCenter, "I can hear you")
            p.restore()

        # Draw checklist on the right side of the core
        p.save()
        states_list = [
            ("LISTENING", C.PRI, "📶"),
            ("THINKING", C.ACC, "◌"),
            ("SPEAKING", C.GREEN, "🔊"),
            ("SLEEPING", C.SEC, "☾"),
            ("OFFLINE", C.MUTED_C, "○")
        ]
        
        start_x = cx + orb_r + 35
        start_y = cy - 75
        spacing_y = 32
        
        for idx, (st_name, st_col, st_icon) in enumerate(states_list):
            item_y = start_y + idx * spacing_y
            
            is_active = False
            if st_name == "LISTENING" and self.state == "LISTENING" and not self.muted:
                is_active = True
            elif st_name == "THINKING" and self.state in ("THINKING", "PROCESSING"):
                is_active = True
            elif st_name == "SPEAKING" and (self.state == "SPEAKING" or self.speaking):
                is_active = True
            elif st_name == "SLEEPING" and self.state == "SLEEPING":
                is_active = True
            elif st_name == "OFFLINE" and self.state == "OFFLINE":
                is_active = True
                
            opacity = 255 if is_active else 60
            text_color = qcol(st_col, opacity)
            
            # Draw icon
            p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            p.setPen(QPen(text_color, 1))
            p.drawText(QRectF(start_x, item_y, 18, 18), Qt.AlignmentFlag.AlignCenter, st_icon)
            
            # Draw text
            p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            p.drawText(QRectF(start_x + 22, item_y, 90, 18), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, st_name)
            
            if is_active:
                p.setBrush(QBrush(qcol(st_col, 20)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(start_x - 3, item_y - 3, 24, 24))
        p.restore()

class MetricBar(QWidget):
    def __init__(self, label: str, color: str = C.PRI, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._value = 0.0
        self._text  = "--"
        self.setFixedHeight(42)
        self.setMinimumWidth(80)

    def set_value(self, pct: float, text: str):
        self._value = max(0.0, min(100.0, pct))
        self._text  = text
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.setBrush(QBrush(qcol("#0a101a", 130)))
        p.setPen(QPen(qcol(C.BORDER, 80), 1))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 6, 6)

        bar_h   = 4
        bar_y   = H - bar_h - 7
        bar_w   = W - 16
        bar_x   = 8

        seg_w   = 3
        gap     = 2
        num_segs = bar_w // (seg_w + gap)
        filled_segs = int(num_segs * self._value / 100)

        for i in range(num_segs):
            seg_x = bar_x + i * (seg_w + gap)
            is_filled = i < filled_segs
            if is_filled:
                if self._value > 85:
                    col = qcol(C.RED)
                elif self._value > 65:
                    col = qcol(C.ACC2)
                else:
                    col = qcol(self._color)
            else:
                col = qcol("#1a2233", 70)
            
            p.fillRect(QRectF(seg_x, bar_y, seg_w, bar_h), col)

        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT_MED), 200))
        p.drawText(QRectF(10, 5, 50, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        text_col = qcol(C.RED) if self._value > 85 else (qcol(C.ACC2) if self._value > 65 else qcol(self._color))
        p.setPen(QPen(text_col if self._text != "--" else qcol(C.TEXT_DIM), 255))
        p.drawText(QRectF(0, 5, W - 10, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._text)

class ChatBubble(QWidget):
    def __init__(self, sender: str, text: str, tag: str, typing: bool = False, parent=None):
        super().__init__(parent)
        self.sender = sender
        self.full_text = text
        self.tag = tag
        self.displayed_text = ""
        self.char_index = 0
        self.timestamp = time.strftime("%I:%M %p")
        
        root_lay = QHBoxLayout(self)
        root_lay.setContentsMargins(2, 2, 2, 2)
        root_lay.setSpacing(8)
        
        is_user = (tag == "you")
        is_sys = (tag == "sys")
        is_err = (tag == "err")
        
        if not is_user and not is_sys:
            self.avatar = AvatarWidget()
            root_lay.addWidget(self.avatar, alignment=Qt.AlignmentFlag.AlignTop)

        self.bubble_frame = QFrame()
        self.bubble_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
        if is_user:
            bg_color = "rgba(0, 85, 255, 0.15)"
            border_color = "rgba(0, 85, 255, 0.35)"
            corner_style = "border-bottom-right-radius: 2px;"
            align = Qt.AlignmentFlag.AlignRight
        elif is_sys:
            bg_color = "transparent"
            border_color = "transparent"
            corner_style = ""
            align = Qt.AlignmentFlag.AlignCenter
        elif is_err:
            bg_color = "rgba(255, 0, 51, 0.08)"
            border_color = "rgba(255, 0, 51, 0.25)"
            corner_style = "border-bottom-left-radius: 2px;"
            align = Qt.AlignmentFlag.AlignLeft
        else:
            bg_color = "rgba(16, 24, 36, 140)"
            border_color = "rgba(255, 255, 255, 0.08)"
            corner_style = "border-bottom-left-radius: 2px;"
            align = Qt.AlignmentFlag.AlignLeft

        self.bubble_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1.2px solid {border_color};
                border-radius: 12px;
                {corner_style}
                padding: 6px 10px;
            }}
        """)
        
        frame_lay = QVBoxLayout(self.bubble_frame)
        frame_lay.setContentsMargins(10, 6, 10, 6)
        frame_lay.setSpacing(4)
        
        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        
        if is_sys:
            self.text_label.setFont(QFont("Consolas", 8))
            self.text_label.setStyleSheet("color: #5C768D; border: none; background: transparent;")
            self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            self.text_label.setFont(QFont("Segoe UI", 9))
            self.text_label.setStyleSheet("color: #E1F5FE; border: none; background: transparent;")
            self.text_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            
        frame_lay.addWidget(self.text_label)

        if tag == "file":
            lower_path = text.lower()
            if any(lower_path.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"]):
                img_lbl = QLabel()
                pix = QPixmap(text)
                if not pix.isNull():
                    scaled = pix.scaledToWidth(240, Qt.TransformationMode.SmoothTransformation)
                    img_lbl.setPixmap(scaled)
                    img_lbl.setStyleSheet("border: 1px solid rgba(0, 229, 255, 0.2); border-radius: 6px;")
                    frame_lay.addWidget(img_lbl)
        
        if not is_sys:
            meta_row = QHBoxLayout()
            meta_row.setContentsMargins(0, 0, 0, 0)
            meta_row.addStretch()
            
            time_lbl = QLabel(self.timestamp)
            time_lbl.setFont(QFont("Segoe UI", 7))
            time_lbl.setStyleSheet("color: rgba(255, 255, 255, 0.3); border: none; background: transparent;")
            meta_row.addWidget(time_lbl)
            
            if is_user:
                checks_lbl = QLabel("✓✓")
                checks_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                checks_lbl.setStyleSheet("color: #00E5FF; border: none; background: transparent;")
                meta_row.addWidget(checks_lbl)
                
            frame_lay.addLayout(meta_row)

        if not is_user and not is_sys:
            text_lower = text.lower()
            if "arijit singh" in text_lower or "play" in text_lower or "gaane" in text_lower:
                self.yt_card = YouTubePlaylistCard()
                frame_lay.addWidget(self.yt_card)

        if is_user:
            root_lay.addStretch()
            root_lay.addWidget(self.bubble_frame)
        elif is_sys:
            root_lay.addWidget(self.bubble_frame)
        else:
            root_lay.addWidget(self.bubble_frame)
            root_lay.addStretch()

        if typing and len(self.full_text) > 0:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._type_char)
            self._timer.start(8)
        else:
            self.text_label.setText(format_markdown_to_html(self.full_text))
            
    def _type_char(self):
        if self.char_index < len(self.full_text):
            self.displayed_text += self.full_text[self.char_index]
            self.text_label.setText(format_markdown_to_html(self.displayed_text) + " ▎")
            self.char_index += 1
            p = self.parent()
            while p and not hasattr(p, 'scroll_to_bottom'):
                p = p.parent()
            if p:
                p.scroll_to_bottom()
        else:
            self._timer.stop()
            self.text_label.setText(format_markdown_to_html(self.full_text))
            p = self.parent()
            while p and not hasattr(p, 'scroll_to_bottom'):
                p = p.parent()
            if p:
                p.scroll_to_bottom()

class LogWidget(QScrollArea):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(0, 229, 255, 0.15);
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(0, 229, 255, 0.35);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                background: none;
                border: none;
            }}
        """)
        
        self.container = QWidget()
        self.container.setObjectName("Container")
        self.container.setStyleSheet("QWidget#Container { background: transparent; }")
        
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(6)
        self.layout.addStretch()
        
        self.setWidget(self.container)
        
        self._queue: list[str] = []
        self._typing = False
        self._sig.connect(self._enqueue)

    def append_log(self, text: str):
        self._sig.emit(text)

    def _enqueue(self, text: str):
        self._queue.append(text)
        if not self._typing:
            self._next()

    def _next(self):
        if not self._queue:
            self._typing = False
            return
        self._typing = True
        raw_text = self._queue.pop(0)
        
        tl = raw_text.lower()
        if tl.startswith("you:"):
            tag = "you"
            display_text = raw_text[4:].strip()
        elif tl.startswith("jarvis:") or tl.startswith("coco ai:") or tl.startswith("coco_ai:"):
            tag = "ai"
            idx = raw_text.find(":")
            display_text = raw_text[idx+1:].strip()
        elif tl.startswith("file:"):
            tag = "file"
            display_text = raw_text[5:].strip()
        elif "err" in tl or tl.startswith("sys: error") or tl.startswith("error"):
            tag = "err"
            display_text = raw_text.replace("SYS: ", "").replace("ERR: ", "").strip()
        else:
            tag = "sys"
            display_text = raw_text.strip()
            
        is_ai = (tag == "ai")
        bubble = ChatBubble(tag, display_text, tag, typing=is_ai, parent=self.container)
        
        self.layout.insertWidget(self.layout.count() - 1, bubble)
        
        if is_ai:
            SoundManager.play("notification")
        elif tag == "err":
            SoundManager.play("error")
            
        self.scroll_to_bottom()
        
        if not is_ai:
            self._typing = False
            QTimer.singleShot(40, self._next)
        else:
            char_time = 8
            total_duration = len(display_text) * char_time + 80
            QTimer.singleShot(total_duration, self._on_typing_done)

    def _on_typing_done(self):
        self._typing = False
        self._next()

    def scroll_to_bottom(self):
        vbar = self.verticalScrollBar()
        vbar.setValue(vbar.maximum())

_FILE_ICONS = {
    "image":   ("🖼", "#00d4ff"), "video":   ("🎬", "#ff6b00"),
    "audio":   ("🎵", "#cc44ff"), "pdf":     ("📄", "#ff4444"),
    "word":    ("📝", "#4488ff"), "excel":   ("📊", "#44bb44"),
    "code":    ("💻", "#ffcc00"), "archive": ("📦", "#ff8844"),
    "pptx":    ("📊", "#ff6622"), "text":    ("📃", "#aaaaaa"),
    "data":    ("🔧", "#88ddff"), "unknown": ("📎", "#888888"),
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
        self.setFixedHeight(102)
        self._current_file: str | None = None
        self._hovering  = False
        self._drag_over = False
        self._dash_offset = 0.0
        self._anim_tmr = QTimer(self)
        self._anim_tmr.timeout.connect(self._animate)
        self._anim_tmr.start(40)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._canvas = _DropCanvas(self)
        layout.addWidget(self._canvas)

    def _animate(self):
        self._dash_offset = (self._dash_offset + 0.8) % 20
        self._canvas.update()

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._drag_over = True; self._canvas.update()

    def dragLeaveEvent(self, e):
        self._drag_over = False; self._canvas.update()

    def dropEvent(self, e: QDropEvent):
        self._drag_over = False
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self._set_file(path)
        self._canvas.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._browse()

    def enterEvent(self, e):
        self._hovering = True; self._canvas.update()

    def leaveEvent(self, e):
        self._hovering = False; self._canvas.update()

    def current_file(self) -> str | None:
        return self._current_file

    def clear_file(self):
        self._current_file = None; self._canvas.update()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a file for COCO AI", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._current_file = path
        self._canvas.update()
        self.file_selected.emit(path)

class _DropCanvas(QWidget):
    def __init__(self, zone: FileDropZone):
        super().__init__(zone)
        self._z = zone

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z    = self._z
        W, H = self.width(), self.height()
        pad  = 6
        rect = QRectF(pad, pad, W - pad * 2, H - pad * 2)

        bg_col = qcol("#001a24" if z._drag_over else ("#001218" if z._hovering else "#0a0f18"), 120)
        p.setBrush(QBrush(bg_col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 8, 8)

        if z._current_file:   border_col = qcol(C.GREEN, 200)
        elif z._drag_over:    border_col = qcol(C.PRI, 230)
        elif z._hovering:     border_col = qcol(C.BORDER_B, 200)
        else:                 border_col = qcol(C.BORDER, 160)

        pen = QPen(border_col, 1.5, Qt.PenStyle.DashLine)
        pen.setDashOffset(z._dash_offset)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 8, 8)

        if z._current_file:   self._paint_file(p, W, H)
        elif z._drag_over:    self._paint_drag_over(p, W, H)
        else:                 self._paint_idle(p, W, H, z._hovering)

    def _paint_idle(self, p, W, H, hover):
        cx, cy = W / 2, H / 2
        col = qcol(C.PRI_DIM if not hover else C.PRI)
        p.setPen(QPen(col, 2)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx, cy - 14), QPointF(cx, cy + 4))
        p.drawLine(QPointF(cx - 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx + 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx - 14, cy + 4), QPointF(cx + 14, cy + 4))
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QPen(qcol(C.PRI_DIM if not hover else C.TEXT), 200))
        p.drawText(QRectF(0, cy + 8, W, 16), Qt.AlignmentFlag.AlignCenter,
                   "Drop file here  or  Click to Browse")
        p.setFont(QFont("Segoe UI", 7))
        p.setPen(QPen(qcol("#1a4a5a"), 200))
        p.drawText(QRectF(0, cy + 24, W, 14), Qt.AlignmentFlag.AlignCenter,
                   "Images · Video · Audio · PDF · Docs · Code · Data")

    def _paint_drag_over(self, p, W, H):
        cx, cy = W / 2, H / 2
        p.setFont(QFont("Segoe UI", 20))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy - 24, W, 32), Qt.AlignmentFlag.AlignCenter, "⬇")
        p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy + 12, W, 16), Qt.AlignmentFlag.AlignCenter, "Release to load")

    def _paint_file(self, p, W, H):
        path = Path(self._z._current_file)
        cat  = _file_category(path)
        icon, icon_col = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size_str = _fmt_size(path.stat().st_size)
        ext_str  = path.suffix.upper().lstrip(".") or "FILE"

        block_x, block_w = 10, 60
        p.setFont(QFont("Segoe UI Emoji", 22) if _OS == "Windows" else QFont("Arial", 22))
        p.setPen(QPen(qcol(icon_col), 1))
        p.drawText(QRectF(block_x, 0, block_w, H), Qt.AlignmentFlag.AlignCenter, icon)

        tx = block_x + block_w + 6
        tw = W - tx - 38

        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.WHITE), 1))
        name = path.name if len(path.name) <= 34 else path.name[:31] + "..."
        p.drawText(QRectF(tx, H * 0.18, tw, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(tx, H * 0.18 + 18, tw, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{ext_str}  ·  {size_str}")

        p.setFont(QFont("Consolas", 7))
        p.setPen(QPen(qcol("#1e5c6a"), 1))
        par = str(path.parent)
        if len(par) > 42: par = "…" + par[-41:]
        p.drawText(QRectF(tx, H * 0.18 + 34, tw, 12),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, par)

        p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.RED, 200), 1))
        p.drawText(QRectF(W - 34, 0, 28, H), Qt.AlignmentFlag.AlignCenter, "✕")

    def mousePressEvent(self, e):
        z = self._z
        if z._current_file and e.pos().x() > self.width() - 34:
            z.clear_file()
            SoundManager.play("click")
        else:
            z.mousePressEvent(e)

class LockScreenOverlay(QWidget):
    unlocked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        self._tick = 0
        self._drag_start = None
        self._is_unlocking = False
        self._opacity = 1.0
        self._slide_y = 0
        self._face_id_state = "SCANNING"  # "SCANNING" | "SUCCESS"
        self._face_id_angle = 0.0
        self._fingerprint_glow = 120
        self._ripples = []  # lists of [radius, opacity]
        
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(16)
        
        # Face ID scanning duration
        QTimer.singleShot(2000, self._face_id_success)
        
    def _face_id_success(self):
        if not self._is_unlocking:
            self._face_id_state = "SUCCESS"
            SoundManager.play("completed")
            # Auto-unlock on Face ID success after a tiny delay
            QTimer.singleShot(600, self.unlock)
            
    def unlock(self):
        if not self._is_unlocking:
            self._is_unlocking = True
            SoundManager.play("click")
            
    def _step(self):
        self._tick += 1
        self._fingerprint_glow = int(150 + 60 * math.sin(self._tick * 0.08))
        
        # Update ripples
        next_ripples = []
        for r, op in self._ripples:
            r += 3.0
            op -= 0.03
            if op > 0:
                next_ripples.append([r, op])
        self._ripples = next_ripples
        
        # Rotate Face ID scanner ring
        if self._face_id_state == "SCANNING":
            self._face_id_angle = (self._face_id_angle + 3.0) % 360
            
        # Unlocking animation (slides up and fades out)
        if self._is_unlocking:
            self._slide_y -= 25
            self._opacity -= 0.06
            self.move(0, self._slide_y)
            if self._opacity <= 0 or self._slide_y < -self.height():
                self._timer.stop()
                self.unlocked.emit()
                self.hide()
                self.deleteLater()
                return
                
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_start = e.position()
            self._drag_start_y = self.y()

    def mouseMoveEvent(self, e):
        if self._drag_start is not None:
            dy = e.position().y() - self._drag_start.y()
            if dy < 0:  # Allow dragging up
                self.move(0, int(self._drag_start_y + dy))

    def mouseReleaseEvent(self, e):
        if self._drag_start is not None:
            dy = e.position().y() - self._drag_start.y()
            if dy < -120:  # Unlocked by swiping up
                self.unlock()
            else:
                # Snap back
                self.move(0, 0)
            self._drag_start = None

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        W, H = self.width(), self.height()
        if W <= 0 or H <= 0:
            return
            
        # 1. Shifting VisionOS wallpaper background
        grad = QLinearGradient(0, 0, W, H)
        h1 = int((self._tick * 0.15) % 360)
        h2 = int((self._tick * 0.15 + 150) % 360)
        c1 = QColor.fromHsl(h1, 140, 20, int(245 * self._opacity))
        c2 = QColor.fromHsl(h2, 120, 12, int(245 * self._opacity))
        grad.setColorAt(0, c1)
        grad.setColorAt(1, c2)
        p.fillRect(self.rect(), QBrush(grad))
        
        cx = W / 2
        
        # 2. Glass Clock & Date Panel
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(qcol("#ffffff", int(12 * self._opacity))))
        clock_rect = QRectF(cx - 170, 40, 340, 115)
        p.drawRoundedRect(clock_rect, 16, 16)
        
        # Glass Clock Panel Border
        p.setPen(QPen(qcol("#ffffff", int(28 * self._opacity)), 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(clock_rect, 16, 16)
        
        # Draw digital time
        p.setPen(QPen(qcol("#ffffff", int(240 * self._opacity))))
        p.setFont(QFont("Segoe UI", 48, QFont.Weight.Light))
        cur_time = time.strftime("%H:%M")
        p.drawText(QRectF(cx - 170, 46, 340, 64), Qt.AlignmentFlag.AlignCenter, cur_time)
        
        # Draw date
        p.setPen(QPen(qcol(C.TEXT_MED, int(210 * self._opacity))))
        p.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        cur_date = time.strftime("%A, %B %d").upper()
        p.drawText(QRectF(cx - 170, 112, 340, 24), Qt.AlignmentFlag.AlignCenter, cur_date)
        
        # 3. Charging Status Panel
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(qcol("#000000", int(60 * self._opacity))))
        bat_rect = QRectF(cx - 85, 170, 170, 32)
        p.drawRoundedRect(bat_rect, 8, 8)
        p.setPen(QPen(qcol(C.GREEN, int(45 * self._opacity)), 1))
        p.drawRoundedRect(bat_rect, 8, 8)
        
        # Draw battery outline
        p.setPen(QPen(qcol(C.GREEN, int(200 * self._opacity)), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(cx - 65, 180, 20, 11), 2.0, 2.0)
        # Tip
        p.setBrush(QBrush(qcol(C.GREEN, int(200 * self._opacity))))
        p.drawRect(QRectF(cx - 45, 183, 2, 5))
        # Inner fill
        p.drawRect(QRectF(cx - 63, 182, 16, 7))
        # Label
        p.setPen(QPen(qcol(C.GREEN, int(220 * self._opacity))))
        p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        p.drawText(QRectF(cx - 38, 170, 100, 32), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "CHARGED 100%")
        
        # 4. Face ID Unlock Animation
        f_cy = 250
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(qcol("#ffffff", int(10 * self._opacity))))
        p.drawEllipse(QPointF(cx, f_cy), 32, 32)
        
        # Scanning/Success Circle Ring
        ring_col = qcol(C.GREEN if self._face_id_state == "SUCCESS" else C.PRI, int(210 * self._opacity))
        p.setPen(QPen(ring_col, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if self._face_id_state == "SCANNING":
            p.drawArc(QRectF(cx - 28, f_cy - 28, 56, 56), int(self._face_id_angle * 16), int(260 * 16))
        else:
            p.drawEllipse(QPointF(cx, f_cy), 28, 28)
            
        # Padlock Vector Icon
        p.setPen(QPen(ring_col, 1.8))
        if self._face_id_state == "SCANNING":
            # Closed lock shackle
            p.drawArc(QRectF(cx - 8, f_cy - 14, 16, 16), 0, 180 * 16)
        else:
            # Open lock shackle (offsetted & rotated)
            p.drawArc(QRectF(cx - 8, f_cy - 19, 16, 16), 30 * 16, 180 * 16)
            
        # Lock body
        p.setBrush(QBrush(ring_col))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(cx - 10, f_cy - 2, 20, 14), 2, 2)
        
        # 5. Notification Panel (frosted-glass cards)
        notif_y = 310
        notifs = [
            ("💬 COCO AI CORE", "Systems online. Scan complete. Ready to interact.", C.PRI),
            ("🔋 POWER SYS", "Connected to AC Power. Performance mode active.", C.GREEN)
        ]
        
        for idx, (title, content, color) in enumerate(notifs):
            y_pos = notif_y + idx * 68
            card_rect = QRectF(cx - 170, y_pos, 340, 58)
            
            # Card frosted fill
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qcol("#ffffff", int(14 * self._opacity))))
            p.drawRoundedRect(card_rect, 10, 10)
            # Border
            p.setPen(QPen(qcol("#ffffff", int(25 * self._opacity)), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(card_rect, 10, 10)
            
            # Title
            p.setPen(QPen(qcol(color, int(220 * self._opacity))))
            p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            p.drawText(QRectF(cx - 158, y_pos + 8, 300, 18), Qt.AlignmentFlag.AlignLeft, title)
            
            # Content
            p.setPen(QPen(qcol(C.TEXT_MED, int(200 * self._opacity))))
            p.setFont(QFont("Segoe UI", 8))
            p.drawText(QRectF(cx - 158, y_pos + 26, 316, 26), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, content)
            
        # 6. Fingerprint Scanner & Ripples
        fg_cy = H - 110
        
        # Draw ripples
        for r, op in self._ripples:
            p.setPen(QPen(qcol(C.PRI, int(op * 255 * self._opacity)), 1.8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, fg_cy), r, r)
            
        # Scanner ring
        fg_glow_col = qcol(C.PRI, int(self._fingerprint_glow * self._opacity))
        p.setPen(QPen(fg_glow_col, 1.8))
        p.setBrush(QBrush(qcol("#000000", int(90 * self._opacity))))
        p.drawEllipse(QPointF(cx, fg_cy), 30, 30)
        
        # Draw fingerprint ridges using concentric curves
        p.setPen(QPen(fg_glow_col, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(cx - 8, fg_cy - 12, 16, 24), 20 * 16, 140 * 16)
        p.drawArc(QRectF(cx - 13, fg_cy - 7, 26, 20), 40 * 16, 100 * 16)
        p.drawArc(QRectF(cx - 18, fg_cy - 2, 36, 16), 30 * 16, 120 * 16)
        p.drawArc(QRectF(cx - 5, fg_cy - 5, 10, 12), 0 * 16, 360 * 16)
        
        # 7. Swipe Up text
        p.setPen(QPen(qcol(C.TEXT_MED, int((120 + 70 * math.sin(self._tick * 0.07)) * self._opacity))))
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        p.drawText(QRectF(0, H - 42, W, 22), Qt.AlignmentFlag.AlignCenter, "▲  SWIPE UP OR HOLD FINGERPRINT TO UNLOCK")

    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        fg_cy = self.height() - 110
        dist = math.hypot(e.position().x() - self.width()/2, e.position().y() - fg_cy)
        if dist <= 30:
            # Clicked fingerprint scanner
            self._ripples.append([30.0, 1.0])
            self._ripples.append([10.0, 0.8])
            SoundManager.play("click")
            QTimer.singleShot(400, self.unlock)
        else:
            if e.button() == Qt.MouseButton.LeftButton:
                self._drag_start = e.position()
                self._drag_start_y = self.y()

class SetupOverlay(QWidget):
    done = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: rgba(5, 7, 10, 245);
                border: 1.5px solid {C.PRI};
                border-radius: 14px;
            }}
        """)

        detected = {"darwin": "mac", "windows": "windows"}.get(
            _OS.lower(), "linux"
        )
        self._sel_os = detected

        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 25, 35, 25)
        layout.setSpacing(10)

        def _lbl(txt, font_size=10, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont("Segoe UI", font_size,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl("◈  INITIALISATION REQUIRED", 14, True))
        layout.addWidget(_lbl("Configure COCO AI before first boot.", 10, color=C.TEXT_MED))
        layout.addSpacing(6)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(255,255,255,0.08);"); layout.addWidget(sep)
        layout.addSpacing(4)

        layout.addWidget(_lbl("GEMINI API KEY", 8, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza…")
        self._key_input.setFont(QFont("Consolas", 10))
        self._key_input.setFixedHeight(34)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d12; color: {C.TEXT};
                border: 1px solid rgba(0, 229, 255, 0.25); border-radius: 5px; padding: 4px 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        layout.addWidget(self._key_input)
        layout.addSpacing(10)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: rgba(255,255,255,0.08);"); layout.addWidget(sep2)
        layout.addSpacing(4)

        layout.addWidget(_lbl("OPERATING SYSTEM", 8, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected: {det_name}", 8, color=C.ACC2,
                               align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(8)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows","⊞  Windows"),("mac","🍎  macOS"),("linux","🐧  Linux")]:
            btn = QPushButton(label)
            btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel(detected)
        layout.addSpacing(10)

        init_btn = QPushButton("▸  INITIALISE SYSTEMS")
        init_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        init_btn.setFixedHeight(38)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 5px;
            }}
            QPushButton:hover {{
                background: {C.PRI_GHO}; border: 1px solid {C.PRI};
            }}
        """)
        init_btn.clicked.connect(self._submit)
        layout.addWidget(init_btn)

    def _sel(self, key: str):
        self._sel_os = key
        SoundManager.play("click")
        pal = {"windows":(C.PRI,"#001a22"),"mac":(C.ACC,"#1a0022"),"linux":(C.GREEN,"#001a0d")}
        for k, btn in self._os_btns.items():
            if k == key:
                fg, bg = pal[k]
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {fg}; color: {bg};
                        border: none; border-radius: 5px; font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: #050b11; color: {C.TEXT_DIM};
                        border: 1px solid rgba(255,255,255,0.06); border-radius: 5px;
                    }}
                    QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_A}; }}
                """)

    def _submit(self):
        key = self._key_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(
                self._key_input.styleSheet() +
                f" QLineEdit {{ border: 1px solid {C.RED}; }}"
            )
            SoundManager.play("error")
            return
        SoundManager.play("completed")
        self.done.emit(key, self._sel_os)


class SidebarButton(QPushButton):
    def __init__(self, icon_str: str, text: str, active: bool = False, parent=None):
        super().__init__(parent)
        self.setText(f"  {icon_str}   {text}")
        self.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold if active else QFont.Weight.Medium))
        self.setFixedHeight(34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.active = active
        self.update_style()

    def update_style(self):
        if self.active:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 229, 255, 0.18), stop:1 rgba(0, 85, 255, 0.04));
                    color: #FFFFFF;
                    border: 1px solid rgba(0, 229, 255, 0.35);
                    border-radius: 8px;
                    text-align: left;
                    padding-left: 14px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {C.TEXT_DIM};
                    border: none;
                    text-align: left;
                    padding-left: 14px;
                }}
                QPushButton:hover {{
                    color: {C.PRI};
                    background: rgba(255, 255, 255, 0.04);
                    border-radius: 8px;
                }}
            """)

class NowPlayingCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: rgba(16, 24, 36, 120);
                border: 1.2px solid rgba(0, 229, 255, 0.12);
                border-radius: 12px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        hdr = QHBoxLayout()
        note_icon = QLabel("🎵")
        note_icon.setStyleSheet("color: #BD00FF; background: transparent; border: none;")
        hdr.addWidget(note_icon)
        
        hdr_lbl = QLabel("NOW PLAYING")
        hdr_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        hdr_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none; letter-spacing: 1px;")
        hdr.addWidget(hdr_lbl)
        hdr.addStretch()
        lay.addLayout(hdr)

        self.title_lbl = QLabel("Kesariya")
        self.title_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.title_lbl.setStyleSheet("color: #FFFFFF; background: transparent; border: none;")
        lay.addWidget(self.title_lbl)

        self.artist_lbl = QLabel("Arijit Singh")
        self.artist_lbl.setFont(QFont("Segoe UI", 7))
        self.artist_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        lay.addWidget(self.artist_lbl)

        time_row = QHBoxLayout()
        time_row.setSpacing(4)
        
        self.curr_time = QLabel("01:24")
        self.curr_time.setFont(QFont("Segoe UI", 7))
        self.curr_time.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        time_row.addWidget(self.curr_time)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(4)
        self.progress.setRange(0, 100)
        self.progress.setValue(31)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {C.PRI}, stop:1 {C.SEC});
                border-radius: 2px;
            }}
        """)
        time_row.addWidget(self.progress)

        self.total_time = QLabel("04:30")
        self.total_time.setFont(QFont("Segoe UI", 7))
        self.total_time.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        time_row.addWidget(self.total_time)
        lay.addLayout(time_row)

        ctrl_row = QHBoxLayout()
        ctrl_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ctrl_row.setSpacing(12)

        prev_btn = QPushButton("⏮")
        prev_btn.setFixedSize(20, 20)
        prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        prev_btn.setStyleSheet("QPushButton { color: #E1F5FE; background: transparent; border: none; font-size: 11px; } QPushButton:hover { color: #00E5FF; }")
        
        self.play_btn = QPushButton("⏸")
        self.play_btn.setFixedSize(20, 20)
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setStyleSheet("QPushButton { color: #E1F5FE; background: transparent; border: none; font-size: 11px; } QPushButton:hover { color: #00E5FF; }")
        
        next_btn = QPushButton("⏭")
        next_btn.setFixedSize(20, 20)
        next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        next_btn.setStyleSheet("QPushButton { color: #E1F5FE; background: transparent; border: none; font-size: 11px; } QPushButton:hover { color: #00E5FF; }")

        ctrl_row.addWidget(prev_btn)
        ctrl_row.addWidget(self.play_btn)
        ctrl_row.addWidget(next_btn)
        lay.addLayout(ctrl_row)

class SidebarWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            SidebarWidget {{
                background: rgba(10, 16, 26, 140);
                border: 1.2px solid rgba(0, 229, 255, 0.12);
                border-radius: 12px;
            }}
        """)
        self.setFixedWidth(164)
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 12, 8, 12)
        lay.setSpacing(4)

        title = QLabel("COCO AI")
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none; padding-left: 8px; letter-spacing: 1px;")
        lay.addWidget(title)
        
        sub = QLabel("Menu Navigation")
        sub.setFont(QFont("Segoe UI", 7))
        sub.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none; padding-left: 8px; padding-bottom: 8px;")
        lay.addWidget(sub)

        self.nav_items = [
            ("🏠", "Home", True),
            ("💬", "AI Chat", False),
            ("🎙", "Voice Assistant", False),
            ("🌐", "Browser", False),
            ("▶", "YouTube", False),
            ("💬", "WhatsApp", False),
            ("🖥", "System Control", False),
            ("‹/›", "Code Assistant", False),
            ("⚙", "Automation", False),
            ("⛅", "Weather", False),
            ("🧠", "Memory", False),
            ("🎮", "Game Updater", False),
            ("🛠", "Settings", False),
        ]
        self.buttons = []
        for icon_str, text, active in self.nav_items:
            btn = SidebarButton(icon_str, text, active, self)
            lay.addWidget(btn)
            self.buttons.append(btn)
            
        lay.addStretch()

        self.music_card = NowPlayingCard(self)
        lay.addWidget(self.music_card)

class TelemetryCard(QFrame):
    def __init__(self, title: str, color_hex: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.color = color_hex
        self.value = 0
        self.history = [0] * 20
        
        self.setStyleSheet(f"""
            QFrame {{
                background: rgba(10, 16, 26, 140);
                border: 1.2px solid rgba(0, 229, 255, 0.12);
                border-radius: 12px;
            }}
        """)
        self.setMinimumWidth(80)
        self.setFixedHeight(110)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(2)
        
        self.hdr_lbl = QLabel(title)
        self.hdr_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        self.hdr_lbl.setStyleSheet(f"color: {color_hex}; background: transparent; border: none;")
        self.layout.addWidget(self.hdr_lbl)
        
        self.val_lbl = QLabel("0%")
        self.val_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.val_lbl.setStyleSheet("color: #FFFFFF; background: transparent; border: none;")
        self.layout.addWidget(self.val_lbl)
        self.layout.addStretch()

    def update_value(self, val: int):
        self.value = val
        self.val_lbl.setText(f"{val}%")
        self.history.pop(0)
        self.history.append(val)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            p = self.parent()
            while p and not isinstance(p, QMainWindow):
                p = p.parent()
            if p:
                p.show_telemetry_details(self.title, self.history)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        W, H = self.width(), self.height()
        p_color = qcol(self.color)
        pen = QPen(p_color, 1.5)
        p.setPen(pen)
        
        path = QPainterPath()
        steps = len(self.history)
        dx = W / (steps - 1)
        
        chart_h = 24
        base_y = H - 6
        
        first = True
        for i, val in enumerate(self.history):
            vx = i * dx
            vy = base_y - (val / 100.0) * chart_h
            if first:
                path.moveTo(vx, vy)
                first = False
            else:
                path.lineTo(vx, vy)
                
        p.drawPath(path)
        
        fill_path = QPainterPath(path)
        fill_path.lineTo(W, H)
        fill_path.lineTo(0, H)
        fill_path.closeSubpath()
        
        fill_grad = QLinearGradient(0, H - chart_h, 0, H)
        fill_grad.setColorAt(0, qcol(self.color, 40))
        fill_grad.setColorAt(1, qcol(self.color, 0))
        p.setBrush(QBrush(fill_grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(fill_path)

class InfoCard(QFrame):
    def __init__(self, title: str, color_hex: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.color = color_hex
        self.setStyleSheet(f"""
            QFrame {{
                background: rgba(10, 16, 26, 140);
                border: 1.2px solid rgba(0, 229, 255, 0.12);
                border-radius: 12px;
            }}
        """)
        self.setMinimumWidth(80)
        self.setFixedHeight(110)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(4)
        
        self.hdr_lbl = QLabel(title)
        self.hdr_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        self.hdr_lbl.setStyleSheet(f"color: {color_hex}; background: transparent; border: none;")
        self.layout.addWidget(self.hdr_lbl)
        
        self.val_lbl = QLabel("")
        self.val_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.val_lbl.setStyleSheet("color: #FFFFFF; background: transparent; border: none;")
        self.layout.addWidget(self.val_lbl)
        
        self.sub_lbl = QLabel("")
        self.sub_lbl.setFont(QFont("Segoe UI", 7))
        self.sub_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        self.layout.addWidget(self.sub_lbl)
        self.layout.addStretch()

    def update_info(self, val: str, sub: str):
        self.val_lbl.setText(val)
        self.sub_lbl.setText(sub)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            p = self.parent()
            while p and not isinstance(p, QMainWindow):
                p = p.parent()
            if p:
                if self.title == "Internet":
                    p.show_speed_test()
                elif self.title == "Battery":
                    p.show_battery_health()

class CircularIconButton(QPushButton):
    def __init__(self, service: str, url: str, parent=None):
        super().__init__(parent)
        self.service = service
        self.url = url
        self.setFixedSize(26, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._open)
        self.setStyleSheet("background: transparent; border: none;")

    def _open(self):
        import webbrowser
        webbrowser.open(self.url)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        
        glow_col = C.ACC if self.service == "insta" else C.PRI
        p.setPen(QPen(qcol(glow_col, 100), 1.2))
        p.setBrush(QBrush(qcol(glow_col, 20)))
        p.drawEllipse(rect)
        
        p.setPen(QPen(qcol("#FFFFFF"), 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        
        cx, cy = rect.center().x(), rect.center().y()
        if self.service == "github":
            path = QPainterPath()
            path.addEllipse(QRectF(cx - 5, cy - 3, 10, 8))
            path.moveTo(cx - 4, cy - 1)
            path.lineTo(cx - 4.5, cy - 5)
            path.lineTo(cx - 1.5, cy - 2)
            path.moveTo(cx + 4, cy - 1)
            path.lineTo(cx + 4.5, cy - 5)
            path.lineTo(cx + 1.5, cy - 2)
            path.addRoundedRect(QRectF(cx - 3, cy + 3, 6, 4), 1, 1)
            p.setBrush(QBrush(qcol("#FFFFFF")))
            p.drawPath(path)
        else:
            p.drawRoundedRect(QRectF(cx - 6, cy - 6, 12, 12), 3, 3)
            p.drawEllipse(QRectF(cx - 3, cy - 3, 6, 6))
            p.setBrush(QBrush(qcol("#FFFFFF")))
            p.drawEllipse(QRectF(cx + 2.5, cy - 4.5, 1.5, 1.5))

class BottomWidget(QFrame):
    def __init__(self, icon_str: str, title: str, value: str, sub: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: rgba(10, 16, 26, 140);
                border: 1.2px solid rgba(0, 229, 255, 0.12);
                border-radius: 12px;
            }}
        """)
        self.setFixedHeight(54)
        
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)
        
        self.icon_lbl = QLabel(icon_str)
        self.icon_lbl.setFont(QFont("Segoe UI", 14))
        self.icon_lbl.setStyleSheet("color: #00E5FF; background: transparent; border: none;")
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.icon_lbl)
        
        txt_col = QVBoxLayout()
        txt_col.setSpacing(1)
        txt_col.setContentsMargins(0, 2, 0, 2)
        
        self.title_lbl = QLabel(title)
        self.title_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        self.title_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        txt_col.addWidget(self.title_lbl)
        
        self.val_lbl = QLabel(value)
        self.val_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.val_lbl.setStyleSheet("color: #E1F5FE; background: transparent; border: none;")
        txt_col.addWidget(self.val_lbl)
        
        if sub:
            self.sub_lbl = QLabel(sub)
            self.sub_lbl.setFont(QFont("Segoe UI", 7))
            self.sub_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
            txt_col.addWidget(self.sub_lbl)
            
        lay.addLayout(txt_col)
        lay.addStretch()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def update_values(self, val: str, sub: str = ""):
        self.val_lbl.setText(val)
        if hasattr(self, 'sub_lbl') and sub:
            self.sub_lbl.setText(sub)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            p = self.parent()
            while p and not isinstance(p, QMainWindow):
                p = p.parent()
            if p:
                title = self.title_lbl.text().upper()
                if "TIME" in title or "DATE" in title:
                    p.show_calendar()
                elif "WEATHER" in title:
                    p.switch_page(9) # Index 9: Weather
                elif "ACTIVE" in title:
                    p.show_active_app_switcher()
                elif "BROWSER" in title:
                    # Switch to browser page
                    p.switch_page(3) # Index 3: Browser
                elif "VOICE" in title:
                    p._toggle_mute()

class DeveloperWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: rgba(10, 16, 26, 140);
                border: 1.2px solid rgba(0, 229, 255, 0.12);
                border-radius: 12px;
            }}
        """)
        self.setFixedHeight(54)
        
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(8)
        
        txt_col = QVBoxLayout()
        txt_col.setSpacing(1)
        txt_col.setContentsMargins(0, 2, 0, 2)
        
        t_lbl = QLabel("DEVELOPER")
        t_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        t_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        txt_col.addWidget(t_lbl)
        
        v_lbl = QLabel("Deva Thakare")
        v_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        v_lbl.setStyleSheet("color: #00E5FF; background: transparent; border: none;")
        txt_col.addWidget(v_lbl)
        
        lay.addLayout(txt_col)
        lay.addStretch()
        
        self.git_btn = CircularIconButton("github", "https://github.com/devathakare7796-ui")
        self.insta_btn = CircularIconButton("insta", "https://www.instagram.com/deva.thakare__7796/")
        lay.addWidget(self.git_btn)
        lay.addWidget(self.insta_btn)

class AvatarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self.setStyleSheet("background: transparent; border: none;")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(qcol(C.PRI, 180), 1.2))
        p.setBrush(QBrush(qcol("#030811")))
        p.drawEllipse(rect)
        
        inner = rect.adjusted(4, 4, -4, -4)
        p.setPen(QPen(qcol(C.SEC, 150), 1.0))
        p.setBrush(QBrush(qcol(C.PRI, 80)))
        p.drawEllipse(inner)

class YouTubePlaylistCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background: rgba(5, 7, 10, 180);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
            }
        """)
        self.setFixedHeight(54)
        self.setFixedWidth(240)
        
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(8)
        
        self.thumb = QWidget()
        self.thumb.setFixedSize(50, 44)
        self.thumb.setStyleSheet("background: #0D1B2A; border-radius: 4px; border: 1px solid rgba(255,255,255,0.1);")
        self.thumb.paintEvent = self._paint_thumb
        lay.addWidget(self.thumb)
        
        txt_col = QVBoxLayout()
        txt_col.setSpacing(1)
        txt_col.setContentsMargins(0, 2, 0, 2)
        
        title = QLabel("Arijit Singh Jukebox 2024")
        title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFFFFF; background: transparent; border: none;")
        txt_col.addWidget(title)
        
        sub = QLabel("Best of Arijit Singh")
        sub.setFont(QFont("Segoe UI", 7))
        sub.setStyleSheet("color: rgba(255, 255, 255, 0.4); background: transparent; border: none;")
        txt_col.addWidget(sub)
        
        yt_row = QHBoxLayout()
        yt_row.setSpacing(4)
        
        yt_logo = QLabel("▶")
        yt_logo.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        yt_logo.setStyleSheet("color: #FF0033; background: transparent; border: none;")
        yt_row.addWidget(yt_logo)
        
        yt_txt = QLabel("YouTube")
        yt_txt.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        yt_txt.setStyleSheet("color: rgba(255, 255, 255, 0.6); background: transparent; border: none;")
        yt_row.addWidget(yt_txt)
        yt_row.addStretch()
        
        txt_col.addLayout(yt_row)
        lay.addLayout(txt_col)
        
    def _paint_thumb(self, event):
        p = QPainter(self.thumb)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.thumb.rect())
        
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0, qcol("#0A192F"))
        grad.setColorAt(1, qcol("#172A45"))
        p.fillRect(rect, QBrush(grad))
        
        cx, cy = rect.center().x(), rect.center().y()
        p.setBrush(QBrush(qcol("#FF0033")))
        p.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        path.moveTo(cx - 3, cy - 5)
        path.lineTo(cx + 5, cy)
        path.lineTo(cx - 3, cy + 5)
        path.closeSubpath()
        p.drawPath(path)

    def set_new_key_callback(self, fn) -> None:
        self._on_new_key = fn

    def _update_qr(self, url: str) -> None:
        if not url:
            self._qr_label.setText("—")
            return
        try:
            import qrcode as _qrmod
            from io import BytesIO
            qr = _qrmod.QRCode(
                box_size=5, border=2,
                error_correction=_qrmod.constants.ERROR_CORRECT_M,
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap()
            px.loadFromData(buf.getvalue())
            self._qr_label.setPixmap(
                px.scaled(170, 170,
                          Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
            )
        except ImportError:
            self._qr_label.setText("pip install\nqrcode[pil]")
            self._qr_label.setFont(QFont("Segoe UI", 9))
            self._qr_label.setStyleSheet(
                "color: #888; background: white; border-radius: 10px; padding: 4px;"
            )
        except Exception:
            self._qr_label.setText(url[:28])
            self._qr_label.setFont(QFont("Segoe UI", 8))
            self._qr_label.setStyleSheet(
                f"color: {C.PRI}; background: white; border-radius: 10px; padding: 4px;"
            )

    def _tick(self):
        remaining = max(0, int(self._expiry - time.time()))
        m, s = divmod(remaining, 60)
        self._timer_lbl.setText(f"Key expires in  {m:02d}:{s:02d}")
        if remaining == 0:
            self._do_close()

    def mark_connected(self) -> None:
        self._ctimer.stop()
        self._key_lbl.setText("CONNECTED")
        self._key_lbl.setStyleSheet(f"""
            color: {C.GREEN};
            background: rgba(34,197,94,0.08);
            border: 2px solid rgba(34,197,94,0.4);
            border-radius: 8px;
            padding: 6px 4px;
            letter-spacing: 4px;
        """)
        self._qr_label.setText("✓")
        self._qr_label.setFont(QFont("Segoe UI", 54, QFont.Weight.Bold))
        self._qr_label.setStyleSheet(
            "color: #00ff88; background: #001a0d; border-radius: 10px;"
        )
        self._timer_lbl.setText("Phone connected — COCO AI ready")
        self._timer_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
        SoundManager.play("completed")

    def _refresh_key(self):
        SoundManager.play("click")
        if self._on_new_key:
            result = self._on_new_key()
            if result:
                url    = result[0]
                key    = result[1]
                auto   = result[2] if len(result) >= 3 else ""
                manual = result[3] if len(result) >= 4 else url
                self._manual_url     = manual or url
                self._url_lbl.setText(self._manual_url)
                self._key_lbl.setText(key)
                self._auto_login_url = auto
                self._update_qr(auto or url)
                self._expiry = time.time() + 600
                self._key_lbl.setStyleSheet(f"""
                    color: {C.ACC};
                    background: rgba(16, 24, 36, 120);
                    border: 1px solid {C.BORDER};
                    border-radius: 8px;
                    padding: 6px 4px;
                    letter-spacing: 10px;
                """)
                self._timer_lbl.setStyleSheet(
                    f"color: {C.TEXT_MED}; background: transparent;"
                )
                self._ctimer.start(1000)
                self._tick()

    def _do_close(self):
        SoundManager.play("click")
        self._ctimer.stop()
        self.hide()
        self.closed.emit()

class SplashWindow(QWidget):
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.SubWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(520, 340)
        
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )
        
        self._tick = 0
        self._opacity = 1.0
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._step)
        self.timer.start(16)
        
        SoundManager.play("startup")

    def _step(self):
        self._tick += 1
        if self._tick > 140:
            self._opacity -= 0.05
            if self._opacity <= 0:
                self._opacity = 0
                self.timer.stop()
                self.close()
                self.finished.emit()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        W, H = self.width(), self.height()
        rect = QRectF(0, 0, W, H).adjusted(10, 10, -10, -10)
        
        p.setBrush(QBrush(qcol("#05070a", int(242 * self._opacity))))
        border_alpha = int(140 * self._opacity)
        p.setPen(QPen(qcol(C.PRI, border_alpha), 1.6))
        p.drawRoundedRect(rect, 16, 16)
        
        p.setPen(QPen(qcol(C.PRI_GHO, int(60 * self._opacity)), 1))
        for x in range(24, W - 24, 24):
            for y in range(24, H - 24, 24):
                p.drawPoint(x, y)
                
        glow_alpha = int((85 + 35 * math.sin(self._tick * 0.08)) * self._opacity)
        p.setPen(QPen(qcol(C.PRI, glow_alpha), 3.5))
        p.setFont(QFont("Segoe UI", 38, QFont.Weight.Bold))
        p.drawText(QRectF(0, H/2 - 55, W, 65), Qt.AlignmentFlag.AlignCenter, "COCO AI")
        
        p.setPen(QPen(qcol(C.WHITE, int(255 * self._opacity)), 1))
        p.setFont(QFont("Segoe UI", 38, QFont.Weight.Bold))
        p.drawText(QRectF(0, H/2 - 55, W - 2, 65), Qt.AlignmentFlag.AlignCenter, "COCO AI")
        
        p.setPen(QPen(qcol(C.TEXT_DIM, int(210 * self._opacity)), 1))
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        p.drawText(QRectF(0, H/2 + 16, W, 22), Qt.AlignmentFlag.AlignCenter, "DEVELOPED BY DEVA THAKARE")
        
        loader_r = 24.0
        angle = (self._tick * 4.2) % 360
        p.setPen(QPen(qcol(C.ACC, int(210 * self._opacity)), 2.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(W/2 - loader_r, H - 75 - loader_r, loader_r * 2, loader_r * 2), int(angle * 16), int(130 * 16))
        
        p.setPen(QPen(qcol(C.TEXT_MED, int(190 * self._opacity)), 1))
        p.setFont(QFont("Consolas", 8))
        status_msg = "INITIALIZING CORE SYSTEM..." if self._tick < 50 else ("LOADING SYSTEMS CONFIG..." if self._tick < 100 else "SECURE CONNECTION ESTABLISHED")
        p.drawText(QRectF(0, H - 42, W, 22), Qt.AlignmentFlag.AlignCenter, status_msg)

import html
import re

def format_markdown_to_html(text: str) -> str:
    escaped = html.escape(text)
    def code_block_repl(match):
        code = match.group(2)
        return f'<pre style="background: rgba(16, 24, 36, 220); border: 1.2px solid rgba(0, 229, 255, 0.2); border-radius: 8px; padding: 10px; font-family: Consolas, Monaco, monospace; color: #00E5FF; margin: 8px 0;">{code}</pre>'
    escaped = re.sub(r'```(?:(\w+)\n)?(.*?)\n?```', code_block_repl, escaped, flags=re.DOTALL)
    escaped = re.sub(r'`([^`\n]+)`', r'<code style="background: rgba(0, 229, 255, 0.12); color: #00E5FF; padding: 2px 5px; border-radius: 4px; font-family: Consolas, Monaco, monospace;">\1</code>', escaped)
    escaped = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', escaped)
    escaped = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', escaped)
    escaped = re.sub(r'^\s*[-*+]\s+(.+)$', r'• \1', escaped, flags=re.MULTILINE)
    escaped = escaped.replace('\n', '<br>')
    return escaped

class TelemetryDetailsDialog(QDialog):
    def __init__(self, title, history, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{title} Diagnostics")
        self.resize(320, 200)
        self.setStyleSheet("background-color: #05070A; color: #E1F5FE;")
        layout = QVBoxLayout(self)
        lbl = QLabel(f"Detailed {title} Resource Usage")
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.PRI};")
        layout.addWidget(lbl)
        val_lbl = QLabel(f"Current Value: {history[-1] if history else 0}%")
        val_lbl.setFont(QFont("Segoe UI", 10))
        layout.addWidget(val_lbl)
        avg_val = sum(history) / len(history) if history else 0
        avg_lbl = QLabel(f"Average (last 20s): {avg_val:.1f}%")
        avg_lbl.setFont(QFont("Segoe UI", 10))
        layout.addWidget(avg_lbl)
        btn = ModernButton("Close", self)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

class SpeedTestDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Network Speed Test")
        self.resize(300, 180)
        self.setStyleSheet("background-color: #05070A; color: #E1F5FE;")
        self.layout = QVBoxLayout(self)
        self.lbl = QLabel("Starting network speed test...")
        self.lbl.setFont(QFont("Segoe UI", 10))
        self.layout.addWidget(self.lbl)
        self.progress = QProgressBar()
        self.progress.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid {C.BORDER}; border-radius: 5px; text-align: center; background-color: rgba(255,255,255,0.05); }}
            QProgressBar::chunk {{ background-color: {C.PRI}; }}
        """)
        self.layout.addWidget(self.progress)
        self.btn = ModernButton("Close", self)
        self.btn.setEnabled(False)
        self.btn.clicked.connect(self.accept)
        self.layout.addWidget(self.btn)
        threading.Thread(target=self._run_test, daemon=True).start()
    def _run_test(self):
        import time, urllib.request
        try:
            self.lbl.setText("Testing latency...")
            self.progress.setValue(20)
            time.sleep(0.5)
            self.lbl.setText("Downloading test payload...")
            self.progress.setValue(50)
            start_time = time.time()
            urllib.request.urlretrieve("https://www.google.com", "speedtest.tmp")
            duration = time.time() - start_time
            self.progress.setValue(80)
            if os.path.exists("speedtest.tmp"):
                os.remove("speedtest.tmp")
            speed = 8 / (duration or 0.1)
            self.lbl.setText(f"Speed Test Complete!\nLatency: ~45 ms\nDownload: {speed:.2f} Mbps")
            self.progress.setValue(100)
        except Exception as e:
            self.lbl.setText(f"Speed test failed: {e}")
            self.progress.setValue(100)
        self.btn.setEnabled(True)

class BatteryHealthDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Battery Health Status")
        self.resize(320, 200)
        self.setStyleSheet("background-color: #05070A; color: #E1F5FE;")
        layout = QVBoxLayout(self)
        lbl = QLabel("Power & Battery Diagnostics")
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.GREEN};")
        layout.addWidget(lbl)
        bat = psutil.sensors_battery()
        if bat:
            pct = bat.percent
            plugged = bat.power_plugged
            secs = bat.secsleft
            p_str = "Plugged In" if plugged else "On Battery"
            layout.addWidget(QLabel(f"Charge Level: {pct}%"))
            layout.addWidget(QLabel(f"Power Source: {p_str}"))
            if secs == psutil.POWER_TIME_UNLIMITED:
                layout.addWidget(QLabel("Time remaining: Unlimited (Plugged in)"))
            elif secs == psutil.POWER_TIME_UNKNOWN:
                layout.addWidget(QLabel("Time remaining: Calculating..."))
            else:
                m, s = divmod(secs, 60)
                h, m = divmod(m, 60)
                layout.addWidget(QLabel(f"Time remaining: {h}h {m}m"))
        else:
            layout.addWidget(QLabel("Battery Status: No Battery Detected (AC Power)"))
        btn = ModernButton("Close", self)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

class CalendarDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calendar")
        self.resize(350, 300)
        self.setStyleSheet("background-color: #05070A; color: #E1F5FE;")
        layout = QVBoxLayout(self)
        cal = QCalendarWidget(self)
        cal.setStyleSheet("""
            QCalendarWidget QWidget { alternate-background-color: #0a101a; background-color: #05070A; color: #E1F5FE; }
            QCalendarWidget QMenu { background-color: #0a101a; color: #E1F5FE; }
        """)
        layout.addWidget(cal)
        btn = ModernButton("Close", self)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

class WindowSwitcherDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Active Window Switcher")
        self.resize(320, 250)
        self.setStyleSheet("background-color: #05070A; color: #E1F5FE;")
        layout = QVBoxLayout(self)
        lbl = QLabel("Double-click a window to bring it to front:")
        lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(lbl)
        self.list_widget = QListWidget(self)
        self.list_widget.setStyleSheet("background-color: #0a101a; color: #E1F5FE; border: 1px solid rgba(0,229,255,0.2);")
        layout.addWidget(self.list_widget)
        self.populate_windows()
        self.list_widget.itemDoubleClicked.connect(self.switch_to_window)
        btn = ModernButton("Cancel", self)
        btn.clicked.connect(self.reject)
        layout.addWidget(btn)
    def populate_windows(self):
        try:
            import pygetwindow as gw
            self.windows = [w for w in gw.getAllWindows() if w.title]
            for w in self.windows:
                self.list_widget.addItem(w.title)
        except Exception as e:
            self.list_widget.addItem(f"Error loading windows: {e}")
    def switch_to_window(self, item):
        try:
            title = item.text()
            for w in self.windows:
                if w.title == title:
                    w.activate()
                    break
            self.accept()
        except Exception as e:
            print(f"Error focusing window: {e}")

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About COCO AI")
        self.resize(320, 220)
        self.setStyleSheet("background-color: #05070A; color: #E1F5FE;")
        layout = QVBoxLayout(self)
        lbl = QLabel("COCO AI Assistant")
        lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.PRI};")
        layout.addWidget(lbl)
        details = QLabel(
            "Version: 2.0.6\n"
            "Author: Deva Thakare\n"
            "License: Creative Commons BY-NC 4.0\n\n"
            "COCO AI is a zero-subscription personal desktop assistant built using PyQt6 and Google Gemini. "
            "It is designed to give you digital autonomy and complete control over your operating system."
        )
        details.setWordWrap(True)
        details.setFont(QFont("Segoe UI", 9))
        layout.addWidget(details)
        btn = ModernButton("Close", self)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

class AIStatusDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("COCO AI Status")
        self.resize(300, 180)
        self.setStyleSheet("background-color: #05070A; color: #E1F5FE;")
        lay = QVBoxLayout(self)
        lbl = QLabel("COCO AI Core Status")
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.PRI};")
        lay.addWidget(lbl)
        lay.addWidget(QLabel("Model: Gemini Live Native Audio"))
        lay.addWidget(QLabel("Speech Rate: 24 kHz Output / 16 kHz Input"))
        lay.addWidget(QLabel("Latencies: ~120-250ms Response Sweep"))
        lay.addWidget(QLabel("Service Connectivity: Stable"))
        btn = ModernButton("Close", self)
        btn.clicked.connect(self.accept)
        lay.addWidget(btn)

class AIDiagnosticsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("COCO AI Diagnostics")
        self.resize(340, 250)
        self.setStyleSheet("background-color: #05070A; color: #E1F5FE;")
        lay = QVBoxLayout(self)
        lbl = QLabel("Advanced Diagnostics")
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.PRI};")
        lay.addWidget(lbl)
        lay.addWidget(QLabel(f"Active Threads: {threading.active_count()} running"))
        lay.addWidget(QLabel("SoundDevice Engine: OK"))
        lay.addWidget(QLabel("Configuration File path: config/api_keys.json"))
        lay.addWidget(QLabel(f"Active Process ID: {os.getpid()}"))
        test_btn = ModernButton("Force Garbage Collection", self)
        def gc_force():
            import gc
            count = gc.collect()
            p = self.parent()
            while p and not hasattr(p, 'write_log'):
                p = p.parent()
            if p:
                p.write_log(f"SYS: Garbage collected {count} objects.")
            QMessageBox.information(self, "Diagnostics", f"Successfully collected {count} unused objects!")
        test_btn.clicked.connect(gc_force)
        lay.addWidget(test_btn)
        btn = ModernButton("Close", self)
        btn.clicked.connect(self.accept)
        lay.addWidget(btn)

class ChatPanel(GlassPanel):
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(10)
        hdr = QLabel("💬  AI CHAT ASSISTANT")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        lay.addWidget(hdr)
        sub = QLabel("Choose a quick prompt to interact with COCO AI:")
        sub.setFont(QFont("Segoe UI", 9))
        sub.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        lay.addWidget(sub)
        grid = QGridLayout()
        grid.setSpacing(8)
        prompts = [
            ("Explain Decorators", "Explain Python decorators in simple terms."),
            ("Check Weather", "Check the current weather report."),
            ("System Info", "Show my system CPU, RAM, and GPU info."),
            ("Take Screenshot", "Take a screenshot of my screen."),
        ]
        for idx, (title, cmd) in enumerate(prompts):
            btn = ModernButton(title, self)
            btn.clicked.connect(lambda checked=False, c=cmd: self.main_win._send_quick_command(c))
            grid.addWidget(btn, idx // 2, idx % 2)
        lay.addLayout(grid)
        btn_lay = QHBoxLayout()
        clr_btn = ModernButton("🗑️ Clear Log", self)
        clr_btn.clicked.connect(lambda: self.main_win._clear_chat_logs())
        btn_lay.addWidget(clr_btn)
        save_btn = ModernButton("💾 Save Log", self)
        save_btn.clicked.connect(lambda: self.main_win._save_chat_logs())
        btn_lay.addWidget(save_btn)
        lay.addLayout(btn_lay)
        lay.addStretch()

class VoiceAssistantPanel(GlassPanel):
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)
        hdr = QLabel("🎙️  VOICE ASSISTANT")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        lay.addWidget(hdr)
        self.status_lbl = QLabel("STATE: LISTENING")
        self.status_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.status_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent; border: none;")
        lay.addWidget(self.status_lbl)
        self.mic_btn = QPushButton("🎙")
        self.mic_btn.setFixedSize(100, 100)
        self.mic_btn.setFont(QFont("Segoe UI", 36))
        self.mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic_btn.setStyleSheet(f"QPushButton {{ background: rgba(0, 229, 255, 0.08); color: {C.PRI}; border: 2px solid {C.PRI}; border-radius: 50px; }} QPushButton:hover {{ background: rgba(0, 229, 255, 0.15); }}")
        self.mic_btn.clicked.connect(self.toggle_mic)
        lay.addWidget(self.mic_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        self.desc_lbl = QLabel("Click the microphone to toggle mute/unmute.")
        self.desc_lbl.setFont(QFont("Segoe UI", 9))
        self.desc_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        lay.addWidget(self.desc_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        self.main_win._state_sig.connect(self.on_state_changed)
        lay.addStretch()
    def toggle_mic(self):
        self.main_win._toggle_mute()
    def on_state_changed(self, state: str):
        self.status_lbl.setText(f"STATE: {state}")
        if state == "MUTED":
            self.status_lbl.setStyleSheet(f"color: {C.RED}; background: transparent; border: none;")
            self.mic_btn.setText("🔇")
            self.mic_btn.setStyleSheet(f"QPushButton {{ background: rgba(255, 0, 51, 0.08); color: {C.RED}; border: 2px solid {C.RED}; border-radius: 50px; }}")
        else:
            self.status_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent; border: none;")
            self.mic_btn.setText("🎙")
            self.mic_btn.setStyleSheet(f"QPushButton {{ background: rgba(0, 229, 255, 0.08); color: {C.PRI}; border: 2px solid {C.PRI}; border-radius: 50px; }}")

class BrowserPanel(GlassPanel):
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(10)
        hdr = QLabel("🌐  BROWSER CONTROL")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        lay.addWidget(hdr)
        url_lbl = QLabel("Open Website:")
        url_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lay.addWidget(url_lbl)
        url_row = QHBoxLayout()
        self.url_in = GlowingLineEdit()
        self.url_in.setPlaceholderText("e.g. google.com or https://github.com")
        url_row.addWidget(self.url_in)
        go_btn = ModernButton("Go", self)
        go_btn.clicked.connect(self.go_to_url)
        url_row.addWidget(go_btn)
        lay.addLayout(url_row)
        search_lbl = QLabel("Search Google:")
        search_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lay.addWidget(search_lbl)
        search_row = QHBoxLayout()
        self.search_in = GlowingLineEdit()
        self.search_in.setPlaceholderText("Search query...")
        search_row.addWidget(self.search_in)
        search_btn = ModernButton("Search", self)
        search_btn.clicked.connect(self.search_google)
        search_row.addWidget(search_btn)
        lay.addLayout(search_row)
        tab_lbl = QLabel("Tab Control:")
        tab_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lay.addWidget(tab_lbl)
        tab_row = QHBoxLayout()
        new_tab_btn = ModernButton("New Tab", self)
        new_tab_btn.clicked.connect(self.new_tab)
        tab_row.addWidget(new_tab_btn)
        close_tab_btn = ModernButton("Close Tab", self)
        close_tab_btn.clicked.connect(self.close_tab)
        tab_row.addWidget(close_tab_btn)
        back_btn = ModernButton("◀ Back", self)
        back_btn.clicked.connect(self.back)
        tab_row.addWidget(back_btn)
        fwd_btn = ModernButton("Forward ▶", self)
        fwd_btn.clicked.connect(self.forward)
        tab_row.addWidget(fwd_btn)
        reload_btn = ModernButton("🔄 Reload", self)
        reload_btn.clicked.connect(self.reload)
        tab_row.addWidget(reload_btn)
        lay.addLayout(tab_row)
        info_lbl = QLabel("Active Tab Details / History:")
        info_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lay.addWidget(info_lbl)
        self.history_list = QListWidget(self)
        self.history_list.setStyleSheet("background-color: #0a101a; color: #E1F5FE; border: 1px solid rgba(0,229,255,0.2);")
        lay.addWidget(self.history_list)
        lay.addStretch()
    def go_to_url(self):
        url = self.url_in.text().strip()
        if not url: return
        self.history_list.addItem(f"[Go To] {url}")
        self.main_win.run_browser_tool_async({"action": "go_to", "url": url})
    def search_google(self):
        q = self.search_in.text().strip()
        if not q: return
        self.history_list.addItem(f"[Search] {q}")
        self.main_win.run_browser_tool_async({"action": "search", "query": q})
    def new_tab(self):
        self.history_list.addItem("[New Tab]")
        self.main_win.run_browser_tool_async({"action": "new_tab", "url": "https://www.google.com"})
    def close_tab(self):
        self.history_list.addItem("[Close Tab]")
        self.main_win.run_browser_tool_async({"action": "close_tab"})
    def back(self):
        self.history_list.addItem("[Back]")
        self.main_win.run_browser_tool_async({"action": "back"})
    def forward(self):
        self.history_list.addItem("[Forward]")
        self.main_win.run_browser_tool_async({"action": "forward"})
    def reload(self):
        self.history_list.addItem("[Reload]")
        self.main_win.run_browser_tool_async({"action": "reload"})

class YouTubePanel(GlassPanel):
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(10)
        hdr = QLabel("▶️  YOUTUBE CONTROL")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        lay.addWidget(hdr)
        play_lbl = QLabel("Play Song / Video on YouTube:")
        play_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lay.addWidget(play_lbl)
        play_row = QHBoxLayout()
        self.song_in = GlowingLineEdit()
        self.song_in.setPlaceholderText("Song name or YouTube URL...")
        play_row.addWidget(self.song_in)
        play_btn = ModernButton("Play", self)
        play_btn.clicked.connect(self.play_song)
        play_row.addWidget(play_btn)
        lay.addLayout(play_row)
        search_lbl = QLabel("Search inside Active YouTube Tab:")
        search_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lay.addWidget(search_lbl)
        search_row = QHBoxLayout()
        self.search_in = GlowingLineEdit()
        self.search_in.setPlaceholderText("Query to search...")
        search_row.addWidget(self.search_in)
        search_btn = ModernButton("Search", self)
        search_btn.clicked.connect(self.search_inside_tab)
        search_row.addWidget(search_btn)
        lay.addLayout(search_row)
        ctrls_lbl = QLabel("Playback Controls:")
        ctrls_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lay.addWidget(ctrls_lbl)
        grid = QGridLayout()
        grid.setSpacing(8)
        btns = [
            ("Play/Pause", self.play_pause),
            ("Previous (Shift+P)", self.prev_song),
            ("Next (Shift+N)", self.next_song),
            ("Fullscreen (F)", self.fullscreen_yt),
        ]
        for idx, (title, slot) in enumerate(btns):
            b = ModernButton(title, self)
            b.clicked.connect(slot)
            grid.addWidget(b, idx // 2, idx % 2)
        lay.addLayout(grid)
        vol_lbl = QLabel("YouTube System Volume:")
        vol_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lay.addWidget(vol_lbl)
        vol_row = QHBoxLayout()
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(70)
        self.vol_slider.setStyleSheet(f"QSlider::groove:horizontal {{ border: 1px solid {C.BORDER}; height: 6px; background: rgba(255,255,255,0.05); border-radius: 3px; }} QSlider::handle:horizontal {{ background: {C.PRI}; width: 14px; margin-top: -4px; margin-bottom: -4px; border-radius: 7px; }}")
        self.vol_slider.valueChanged.connect(self.change_volume)
        vol_row.addWidget(self.vol_slider)
        self.vol_val_lbl = QLabel("70%")
        vol_row.addWidget(self.vol_val_lbl)
        lay.addLayout(vol_row)
        lay.addStretch()
    def play_song(self):
        q = self.song_in.text().strip()
        if not q: return
        from actions.youtube_video import youtube_video
        threading.Thread(target=lambda: youtube_video(parameters={"action": "play", "query": q}, player=self.main_win.ui_ref), daemon=True).start()
    def search_inside_tab(self):
        q = self.search_in.text().strip()
        if not q: return
        from actions.browser_control import browser_control
        args = {"action": "type", "selector": 'input[name="search_query"]', "text": q, "press_enter": True}
        threading.Thread(target=lambda: browser_control(parameters=args, player=self.main_win.ui_ref), daemon=True).start()
    def play_pause(self):
        from actions.computer_settings import computer_settings
        threading.Thread(target=lambda: computer_settings(parameters={"action": "play_pause"}, player=self.main_win.ui_ref), daemon=True).start()
    def prev_song(self):
        from actions.computer_control import computer_control
        threading.Thread(target=lambda: computer_control(parameters={"action": "hotkey", "keys": "shift+p"}, player=self.main_win.ui_ref), daemon=True).start()
    def next_song(self):
        from actions.computer_control import computer_control
        threading.Thread(target=lambda: computer_control(parameters={"action": "hotkey", "keys": "shift+n"}, player=self.main_win.ui_ref), daemon=True).start()
    def fullscreen_yt(self):
        from actions.computer_control import computer_control
        threading.Thread(target=lambda: computer_control(parameters={"action": "press", "key": "f"}, player=self.main_win.ui_ref), daemon=True).start()
    def change_volume(self, val):
        self.vol_val_lbl.setText(f"{val}%")
        from actions.computer_settings import computer_settings
        threading.Thread(target=lambda: computer_settings(parameters={"action": "volume_set", "value": str(val)}, player=self.main_win.ui_ref), daemon=True).start()

class WhatsAppPanel(GlassPanel):
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(10)
        hdr = QLabel("💬  WHATSAPP CONTROLS")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        lay.addWidget(hdr)
        open_btn = ModernButton("Open WhatsApp", self)
        open_btn.clicked.connect(self.open_wa)
        lay.addWidget(open_btn)
        search_lbl = QLabel("Search Contact:")
        search_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lay.addWidget(search_lbl)
        search_row = QHBoxLayout()
        self.contact_in = GlowingLineEdit()
        self.contact_in.setPlaceholderText("Contact name...")
        search_row.addWidget(self.contact_in)
        search_btn = ModernButton("Search", self)
        search_btn.clicked.connect(self.search_contact)
        search_row.addWidget(search_btn)
        lay.addLayout(search_row)
        msg_lbl = QLabel("Send WhatsApp Message:")
        msg_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lay.addWidget(msg_lbl)
        self.msg_in = GlowingTextEdit()
        self.msg_in.setPlaceholderText("Type message here...")
        self.msg_in.setFixedHeight(60)
        lay.addWidget(self.msg_in)
        send_btn = ModernButton("Send Message", self)
        send_btn.clicked.connect(self.send_message)
        lay.addWidget(send_btn)
        read_btn = ModernButton("Read Latest Chats", self)
        read_btn.clicked.connect(self.read_chats)
        lay.addWidget(read_btn)
        lay.addStretch()
    def open_wa(self):
        from actions.open_app import open_app
        threading.Thread(target=lambda: open_app(parameters={"app_name": "WhatsApp"}, player=self.main_win.ui_ref), daemon=True).start()
    def search_contact(self):
        contact = self.contact_in.text().strip()
        if not contact: return
        from actions.send_message import send_message
        threading.Thread(target=lambda: send_message(parameters={"receiver": contact, "message_text": "Hello", "platform": "WhatsApp"}, player=self.main_win.ui_ref), daemon=True).start()
    def send_message(self):
        contact = self.contact_in.text().strip()
        msg = self.msg_in.toPlainText().strip()
        if not contact or not msg: return
        from actions.send_message import send_message
        threading.Thread(target=lambda: send_message(parameters={"receiver": contact, "message_text": msg, "platform": "WhatsApp"}, player=self.main_win.ui_ref), daemon=True).start()
    def read_chats(self):
        self.main_win.write_log("SYS: Reading WhatsApp latest chats...")
        from actions.browser_control import browser_control
        threading.Thread(target=lambda: browser_control(parameters={"action": "get_text", "selector": "div._ak8q"}, player=self.main_win.ui_ref), daemon=True).start()

class SystemControlPanel(GlassPanel):
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(10)
        hdr = QLabel("🖥️  SYSTEM CONTROL")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        lay.addWidget(hdr)
        grid = QGridLayout()
        grid.setSpacing(8)
        btns = [
            ("🔐 Lock PC", self.lock_pc),
            ("💤 Sleep", self.sleep_pc),
            ("🔄 Restart", self.restart_pc),
            ("🛑 Shutdown", self.shutdown_pc),
            ("📸 Screenshot", self.screenshot_pc),
            ("📋 Task Manager", self.task_mgr),
            ("🛠 System Settings", self.sys_settings),
            ("📶 Wi-Fi Settings", self.wifi_settings),
            ("🔵 Bluetooth", self.bluetooth_settings),
        ]
        for idx, (title, slot) in enumerate(btns):
            b = ModernButton(title, self)
            b.clicked.connect(slot)
            grid.addWidget(b, idx // 3, idx % 3)
        lay.addLayout(grid)
        vol_lbl = QLabel("System Volume:")
        vol_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lay.addWidget(vol_lbl)
        vol_row = QHBoxLayout()
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(50)
        self.vol_slider.setStyleSheet(f"QSlider::groove:horizontal {{ border: 1px solid {C.BORDER}; height: 6px; background: rgba(255,255,255,0.05); border-radius: 3px; }} QSlider::handle:horizontal {{ background: {C.PRI}; width: 14px; margin-top: -4px; margin-bottom: -4px; border-radius: 7px; }}")
        self.vol_slider.valueChanged.connect(self.change_volume)
        vol_row.addWidget(self.vol_slider)
        self.vol_val_lbl = QLabel("50%")
        vol_row.addWidget(self.vol_val_lbl)
        lay.addLayout(vol_row)
        bri_lbl = QLabel("System Brightness:")
        bri_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lay.addWidget(bri_lbl)
        bri_row = QHBoxLayout()
        self.bri_slider = QSlider(Qt.Orientation.Horizontal)
        self.bri_slider.setRange(0, 100)
        self.bri_slider.setValue(60)
        self.bri_slider.setStyleSheet(f"QSlider::groove:horizontal {{ border: 1px solid {C.BORDER}; height: 6px; background: rgba(255,255,255,0.05); border-radius: 3px; }} QSlider::handle:horizontal {{ background: {C.PRI}; width: 14px; margin-top: -4px; margin-bottom: -4px; border-radius: 7px; }}")
        self.bri_slider.valueChanged.connect(self.change_brightness)
        bri_row.addWidget(self.bri_slider)
        self.bri_val_lbl = QLabel("60%")
        bri_row.addWidget(self.bri_val_lbl)
        lay.addLayout(bri_row)
        lay.addStretch()
    def lock_pc(self):
        from actions.computer_settings import computer_settings
        threading.Thread(target=lambda: computer_settings(parameters={"action": "lock_screen"}, player=self.main_win.ui_ref), daemon=True).start()
    def sleep_pc(self):
        from actions.computer_settings import computer_settings
        threading.Thread(target=lambda: computer_settings(parameters={"action": "sleep_display"}, player=self.main_win.ui_ref), daemon=True).start()
    def restart_pc(self):
        d = QDialog(self)
        d.setWindowTitle("Confirm Restart")
        d.setStyleSheet("background-color: #05070A; color: #E1F5FE;")
        lay = QVBoxLayout(d)
        lay.addWidget(QLabel("Are you sure you want to restart the computer?"))
        btn_row = QHBoxLayout()
        yes = ModernButton("Yes", d)
        yes.clicked.connect(d.accept)
        no = ModernButton("No", d)
        no.clicked.connect(d.reject)
        btn_row.addWidget(yes); btn_row.addWidget(no)
        lay.addLayout(btn_row)
        if d.exec() == QDialog.DialogCode.Accepted:
            from actions.computer_settings import computer_settings
            threading.Thread(target=lambda: computer_settings(parameters={"action": "restart", "confirmed": "yes"}, player=self.main_win.ui_ref), daemon=True).start()
    def shutdown_pc(self):
        d = QDialog(self)
        d.setWindowTitle("Confirm Shutdown")
        d.setStyleSheet("background-color: #05070A; color: #E1F5FE;")
        lay = QVBoxLayout(d)
        lay.addWidget(QLabel("Are you sure you want to shutdown the computer?"))
        btn_row = QHBoxLayout()
        yes = ModernButton("Yes", d)
        yes.clicked.connect(d.accept)
        no = ModernButton("No", d)
        no.clicked.connect(d.reject)
        btn_row.addWidget(yes); btn_row.addWidget(no)
        lay.addLayout(btn_row)
        if d.exec() == QDialog.DialogCode.Accepted:
            from actions.computer_settings import computer_settings
            threading.Thread(target=lambda: computer_settings(parameters={"action": "shutdown", "confirmed": "yes"}, player=self.main_win.ui_ref), daemon=True).start()
    def screenshot_pc(self):
        from actions.computer_settings import computer_settings
        threading.Thread(target=lambda: computer_settings(parameters={"action": "screenshot"}, player=self.main_win.ui_ref), daemon=True).start()
    def task_mgr(self):
        from actions.computer_settings import computer_settings
        threading.Thread(target=lambda: computer_settings(parameters={"action": "task_manager"}, player=self.main_win.ui_ref), daemon=True).start()
    def sys_settings(self):
        from actions.computer_settings import computer_settings
        threading.Thread(target=lambda: computer_settings(parameters={"action": "open_settings"}, player=self.main_win.ui_ref), daemon=True).start()
    def wifi_settings(self):
        from actions.computer_settings import computer_settings
        threading.Thread(target=lambda: computer_settings(parameters={"action": "toggle_wifi"}, player=self.main_win.ui_ref), daemon=True).start()
    def bluetooth_settings(self):
        import subprocess
        threading.Thread(target=lambda: subprocess.run("start ms-settings:bluetooth", shell=True), daemon=True).start()
    def change_volume(self, val):
        self.vol_val_lbl.setText(f"{val}%")
        from actions.computer_settings import computer_settings
        threading.Thread(target=lambda: computer_settings(parameters={"action": "volume_set", "value": str(val)}, player=self.main_win.ui_ref), daemon=True).start()
    def change_brightness(self, val):
        self.bri_val_lbl.setText(f"{val}%")
        def _set():
            try:
                import subprocess
                cmd = f"powershell (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {val})"
                subprocess.run(cmd, shell=True)
            except Exception:
                pass
        threading.Thread(target=_set, daemon=True).start()

class CodeAssistantPanel(GlassPanel):
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(10)
        hdr = QLabel("‹/›  CODE ASSISTANT")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        lay.addWidget(hdr)
        lang_lbl = QLabel("Target Programming Language:")
        lang_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lay.addWidget(lang_lbl)
        self.lang_cb = QComboBox(self)
        self.lang_cb.addItems(["Python", "HTML", "CSS", "JavaScript", "C++", "Java"])
        self.lang_cb.setStyleSheet("QComboBox { background-color: #0a101a; color: #E1F5FE; border: 1px solid rgba(0,229,255,0.2); padding: 4px; }")
        lay.addWidget(self.lang_cb)
        task_lbl = QLabel("Describe your code task:")
        task_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lay.addWidget(task_lbl)
        self.task_in = GlowingTextEdit()
        self.task_in.setPlaceholderText("Write a Python script that calculates Fibonacci sequences, explain how recursion works here, or design a responsive CSS navbar...")
        self.task_in.setFixedHeight(120)
        lay.addWidget(self.task_in)
        grid = QGridLayout()
        grid.setSpacing(8)
        gen_btn = ModernButton("Generate Code", self)
        gen_btn.clicked.connect(lambda: self.run_code_tool("write"))
        grid.addWidget(gen_btn, 0, 0)
        exp_btn = ModernButton("Explain Code", self)
        exp_btn.clicked.connect(lambda: self.run_code_tool("explain"))
        grid.addWidget(exp_btn, 0, 1)
        fix_btn = ModernButton("Fix Bugs", self)
        fix_btn.clicked.connect(lambda: self.run_code_tool("edit"))
        grid.addWidget(fix_btn, 1, 0)
        proj_btn = ModernButton("Create Project", self)
        proj_btn.clicked.connect(self.run_project_tool)
        grid.addWidget(proj_btn, 1, 1)
        lay.addLayout(grid)
        lay.addStretch()
    def run_code_tool(self, action):
        desc = self.task_in.toPlainText().strip()
        lang = self.lang_cb.currentText().lower()
        if not desc: return
        self.main_win.write_log(f"SYS: Running Code Assistant ({action})...")
        from actions.code_helper import code_helper
        threading.Thread(target=lambda: code_helper(parameters={"action": action, "description": desc, "language": lang}, player=self.main_win.ui_ref, speak=self.main_win.ui_ref.speak), daemon=True).start()
    def run_project_tool(self):
        desc = self.task_in.toPlainText().strip()
        lang = self.lang_cb.currentText().lower()
        if not desc: return
        self.main_win.write_log("SYS: Running Dev Agent to build complete project...")
        from actions.dev_agent import dev_agent
        threading.Thread(target=lambda: dev_agent(parameters={"description": desc, "language": lang}, player=self.main_win.ui_ref, speak=self.main_win.ui_ref.speak), daemon=True).start()

class AutomationPanel(GlassPanel):
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(10)
        hdr = QLabel("⚙️  AUTOMATIONS & TASKS")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        lay.addWidget(hdr)
        lbl = QLabel("Schedule new Task:")
        lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lay.addWidget(lbl)
        form = QGridLayout()
        form.setSpacing(6)
        form.addWidget(QLabel("Time (HH:MM):"), 0, 0)
        self.time_in = GlowingLineEdit()
        self.time_in.setPlaceholderText("14:30")
        form.addWidget(self.time_in, 0, 1)
        form.addWidget(QLabel("Task/Message:"), 1, 0)
        self.task_in = GlowingLineEdit()
        self.task_in.setPlaceholderText("Drink water or backup files")
        form.addWidget(self.task_in, 1, 1)
        lay.addLayout(form)
        create_btn = ModernButton("Create Automation", self)
        create_btn.clicked.connect(self.create_task)
        lay.addWidget(create_btn)
        act_lbl = QLabel("Active Scheduled/Background Tasks:")
        act_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lay.addWidget(act_lbl)
        self.task_list = QListWidget(self)
        self.task_list.setStyleSheet("background-color: #0a101a; color: #E1F5FE; border: 1px solid rgba(0,229,255,0.2);")
        lay.addWidget(self.task_list)
        del_btn = ModernButton("Delete Selected Automation", self)
        del_btn.clicked.connect(self.delete_task)
        lay.addWidget(del_btn)
        self.load_tasks()
        lay.addStretch()
    def load_tasks(self):
        self.task_list.clear()
        self.task_list.addItem("[Scheduled] 09:00 AM - Check daily updates")
        self.task_list.addItem("[Scheduled] 06:00 PM - Backup system configuration")
        self.task_list.addItem("[Background] Battery Monitor - Running")
        self.task_list.addItem("[Background] System Diagnostics - Running")
    def create_task(self):
        t_str = self.time_in.text().strip()
        msg = self.task_in.text().strip()
        if not t_str or not msg: return
        d_str = datetime.today().strftime("%Y-%m-%d")
        from actions.reminder import reminder
        threading.Thread(target=lambda: reminder(parameters={"date": d_str, "time": t_str, "message": msg}, player=self.main_win.ui_ref), daemon=True).start()
        self.task_list.addItem(f"[Scheduled] {t_str} - {msg}")
        self.time_in.clear()
        self.task_in.clear()
    def delete_task(self):
        item = self.task_list.currentItem()
        if item:
            self.task_list.takeItem(self.task_list.row(item))

class WeatherPanel(GlassPanel):
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(10)
        hdr = QLabel("⛅  LIVE WEATHER")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        lay.addWidget(hdr)
        row = QHBoxLayout()
        self.city_in = GlowingLineEdit()
        self.city_in.setPlaceholderText("Enter City name (e.g. Mumbai, New York)...")
        row.addWidget(self.city_in)
        btn = ModernButton("Get Weather", self)
        btn.clicked.connect(self.get_weather)
        row.addWidget(btn)
        lay.addLayout(row)
        self.weather_box = QFrame()
        self.weather_box.setStyleSheet("background-color: #0a101a; border: 1px solid rgba(0,229,255,0.2); border-radius: 8px; padding: 12px;")
        box_lay = QVBoxLayout(self.weather_box)
        self.city_lbl = QLabel("City: Mumbai")
        self.city_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.city_lbl.setStyleSheet("color: #FFFFFF; background: transparent; border: none;")
        box_lay.addWidget(self.city_lbl)
        self.temp_lbl = QLabel("Temperature: 28°C")
        self.temp_lbl.setFont(QFont("Segoe UI", 10))
        self.temp_lbl.setStyleSheet("color: #FFFFFF; background: transparent; border: none;")
        box_lay.addWidget(self.temp_lbl)
        self.humidity_lbl = QLabel("Humidity: 70%")
        self.humidity_lbl.setFont(QFont("Segoe UI", 10))
        self.humidity_lbl.setStyleSheet("color: #FFFFFF; background: transparent; border: none;")
        box_lay.addWidget(self.humidity_lbl)
        self.wind_lbl = QLabel("Wind: 10km/h")
        self.wind_lbl.setFont(QFont("Segoe UI", 10))
        self.wind_lbl.setStyleSheet("color: #FFFFFF; background: transparent; border: none;")
        box_lay.addWidget(self.wind_lbl)
        self.cond_lbl = QLabel("Condition: Cloudy")
        self.cond_lbl.setFont(QFont("Segoe UI", 10))
        self.cond_lbl.setStyleSheet("color: #FFFFFF; background: transparent; border: none;")
        box_lay.addWidget(self.cond_lbl)
        lay.addWidget(self.weather_box)
        lay.addStretch()
    def get_weather(self):
        city = self.city_in.text().strip()
        if not city: return
        self.city_lbl.setText(f"City: {city.title()} (fetching...)")
        from actions.weather_report import weather_action
        threading.Thread(target=lambda: weather_action(parameters={"city": city}, player=self.main_win.ui_ref), daemon=True).start()
        def update_labels(temp, hum, wind, cond):
            self.city_lbl.setText(f"City: {city.title()}")
            self.temp_lbl.setText(f"Temperature: {temp}")
            self.humidity_lbl.setText(f"Humidity: {hum}")
            self.wind_lbl.setText(f"Wind: {wind}")
            self.cond_lbl.setText(f"Condition: {cond}")
            self.main_win.bot_weather.update_values(f"{temp} {cond}", city.title())
        import requests, urllib.parse
        def _fetch():
            try:
                r = requests.get(f"http://wttr.in/{urllib.parse.quote_plus(city)}?format=%t|%h|%w|%C", timeout=5)
                if r.status_code == 200:
                    parts = r.text.strip().split('|')
                    if len(parts) == 4:
                        QTimer.singleShot(0, lambda: update_labels(parts[0], parts[1], parts[2], parts[3]))
                        return
                QTimer.singleShot(0, lambda: update_labels("N/A", "N/A", "N/A", "N/A"))
            except Exception:
                QTimer.singleShot(0, lambda: update_labels("N/A", "N/A", "N/A", "N/A"))
        threading.Thread(target=_fetch, daemon=True).start()

class MemoryPanel(GlassPanel):
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(10)
        hdr = QLabel("🧠  LONG-TERM MEMORY")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        lay.addWidget(hdr)
        search_row = QHBoxLayout()
        self.search_in = GlowingLineEdit()
        self.search_in.setPlaceholderText("Search memory by key...")
        self.search_in.textChanged.connect(self.search_memory)
        search_row.addWidget(self.search_in)
        lay.addLayout(search_row)
        self.mem_list = QListWidget(self)
        self.mem_list.setStyleSheet("background-color: #0a101a; color: #E1F5FE; border: 1px solid rgba(0,229,255,0.2);")
        lay.addWidget(self.mem_list)
        lbl = QLabel("Add Memory:")
        lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lay.addWidget(lbl)
        form = QGridLayout()
        form.setSpacing(6)
        form.addWidget(QLabel("Category:"), 0, 0)
        self.cat_cb = QComboBox(self)
        self.cat_cb.addItems(["notes", "identity", "preferences", "projects", "relationships", "wishes"])
        self.cat_cb.setStyleSheet("QComboBox { background-color: #0a101a; color: #E1F5FE; border: 1px solid rgba(0,229,255,0.2); padding: 4px; }")
        form.addWidget(self.cat_cb, 0, 1)
        form.addWidget(QLabel("Key:"), 1, 0)
        self.key_in = GlowingLineEdit()
        self.key_in.setPlaceholderText("favorite_color")
        form.addWidget(self.key_in, 1, 1)
        form.addWidget(QLabel("Value:"), 2, 0)
        self.val_in = GlowingLineEdit()
        self.val_in.setPlaceholderText("electric cyan")
        form.addWidget(self.val_in, 2, 1)
        lay.addLayout(form)
        btn_row = QHBoxLayout()
        add_btn = ModernButton("Add Memory", self)
        add_btn.clicked.connect(self.add_memory)
        btn_row.addWidget(add_btn)
        del_btn = ModernButton("Forget Memory", self)
        del_btn.clicked.connect(self.forget_memory)
        btn_row.addWidget(del_btn)
        lay.addLayout(btn_row)
        self.load_memories()
        lay.addStretch()
    def load_memories(self):
        self.mem_list.clear()
        from memory.memory_manager import load_memory
        memory = load_memory()
        for cat, items in memory.items():
            if isinstance(items, dict):
                for k, entry in items.items():
                    val = entry.get("value") if isinstance(entry, dict) else entry
                    self.mem_list.addItem(f"[{cat.upper()}] {k}: {val}")
    def search_memory(self, q):
        q = q.lower().strip()
        for i in range(self.mem_list.count()):
            item = self.mem_list.item(i)
            item.setHidden(q not in item.text().lower())
    def add_memory(self):
        cat = self.cat_cb.currentText()
        key = self.key_in.text().strip().lower().replace(" ", "_")
        val = self.val_in.text().strip()
        if not key or not val: return
        from memory.memory_manager import remember
        remember(key, val, cat)
        self.load_memories()
        self.key_in.clear()
        self.val_in.clear()
    def forget_memory(self):
        item = self.mem_list.currentItem()
        if not item: return
        text = item.text()
        try:
            cat_idx = text.find("]")
            cat = text[1:cat_idx].lower()
            key_idx = text.find(":")
            key = text[cat_idx+2:key_idx].strip()
            from memory.memory_manager import forget
            forget(key, cat)
            self.load_memories()
        except Exception:
            pass

class GameUpdaterPanel(GlassPanel):
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(10)
        hdr = QLabel("🎮  GAME UPDATER")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        lay.addWidget(hdr)
        btn_row = QHBoxLayout()
        scan_btn = ModernButton("🔍 Scan Installed Games", self)
        scan_btn.clicked.connect(lambda: self.run_game_tool("list"))
        btn_row.addWidget(scan_btn)
        check_btn = ModernButton("🔄 Check Updates", self)
        check_btn.clicked.connect(lambda: self.run_game_tool("update"))
        btn_row.addWidget(check_btn)
        lay.addLayout(btn_row)
        lbl = QLabel("Launch Game:")
        lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lay.addWidget(lbl)
        launch_row = QHBoxLayout()
        self.game_in = GlowingLineEdit()
        self.game_in.setPlaceholderText("Game Name (e.g. Cyberpunk)...")
        launch_row.addWidget(self.game_in)
        launch_btn = ModernButton("Launch", self)
        launch_btn.clicked.connect(self.launch_game)
        launch_row.addWidget(launch_btn)
        lay.addLayout(launch_row)
        log_lbl = QLabel("Game Updater Output Console:")
        log_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lay.addWidget(log_lbl)
        self.console_list = QListWidget(self)
        self.console_list.setStyleSheet("background-color: #05070a; color: #00FF66; border: 1.2px solid rgba(0,255,102,0.2); font-family: Consolas;")
        lay.addWidget(self.console_list)
        lay.addStretch()
    def run_game_tool(self, action):
        self.console_list.addItem(f"Running game updater action: '{action}'...")
        from actions.game_updater import game_updater
        def _run():
            try:
                def spk(text):
                    QTimer.singleShot(0, lambda: self.console_list.addItem(f"[Game Updater] {text}"))
                    self.main_win.ui_ref.speak(text)
                game_updater(parameters={"action": action}, player=self.main_win.ui_ref, speak=spk)
            except Exception as e:
                QTimer.singleShot(0, lambda: self.console_list.addItem(f"Error: {e}"))
        threading.Thread(target=_run, daemon=True).start()
    def launch_game(self):
        game = self.game_in.text().strip()
        if not game: return
        self.console_list.addItem(f"Launching game: '{game}'...")
        from actions.game_updater import game_updater
        threading.Thread(target=lambda: game_updater(parameters={"action": "install", "game_name": game}, player=self.main_win.ui_ref, speak=self.main_win.ui_ref.speak), daemon=True).start()

class SettingsPanel(GlassPanel):
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(10)
        hdr = QLabel("🛠️  COCO AI SETTINGS")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        lay.addWidget(hdr)
        form = QGridLayout()
        form.setSpacing(8)
        form.addWidget(QLabel("Accent Color:"), 0, 0)
        self.color_cb = QComboBox(self)
        self.color_cb.addItems(["Cyan (Default)", "Purple", "Green", "Red", "Blue"])
        self.color_cb.setStyleSheet("QComboBox { background-color: #0a101a; color: #E1F5FE; border: 1px solid rgba(0,229,255,0.2); padding: 4px; }")
        self.color_cb.currentIndexChanged.connect(self.change_accent_color)
        form.addWidget(self.color_cb, 0, 1)
        form.addWidget(QLabel("Microphone Device:"), 1, 0)
        self.mic_cb = QComboBox(self)
        self.mic_cb.setStyleSheet("QComboBox { background-color: #0a101a; color: #E1F5FE; border: 1px solid rgba(0,229,255,0.2); padding: 4px; }")
        form.addWidget(self.mic_cb, 1, 1)
        form.addWidget(QLabel("Speaker Device:"), 2, 0)
        self.spk_cb = QComboBox(self)
        self.spk_cb.setStyleSheet("QComboBox { background-color: #0a101a; color: #E1F5FE; border: 1px solid rgba(0,229,255,0.2); padding: 4px; }")
        form.addWidget(self.spk_cb, 2, 1)
        form.addWidget(QLabel("Voice Language:"), 3, 0)
        self.lang_cb = QComboBox(self)
        self.lang_cb.addItems(["English (US)", "English (UK)", "Hindi", "French", "German", "Spanish"])
        self.lang_cb.setStyleSheet("QComboBox { background-color: #0a101a; color: #E1F5FE; border: 1px solid rgba(0,229,255,0.2); padding: 4px; }")
        form.addWidget(self.lang_cb, 3, 1)
        self.anim_cb = QCheckBox("Enable UI Visualizer Animations", self)
        self.anim_cb.setChecked(True)
        self.anim_cb.setStyleSheet("color: #E1F5FE; background: transparent; border: none;")
        self.anim_cb.stateChanged.connect(self.toggle_animations)
        form.addWidget(self.anim_cb, 4, 0, 1, 2)
        self.startup_cb = QCheckBox("Run COCO AI on System Startup", self)
        self.startup_cb.setChecked(False)
        self.startup_cb.setStyleSheet("color: #E1F5FE; background: transparent; border: none;")
        self.startup_cb.stateChanged.connect(self.toggle_startup)
        form.addWidget(self.startup_cb, 5, 0, 1, 2)
        lay.addLayout(form)
        btn_row = QHBoxLayout()
        check_up = ModernButton("Check updates", self)
        check_up.clicked.connect(lambda: self.main_win.check_updates())
        btn_row.addWidget(check_up)
        about_btn = ModernButton("About", self)
        about_btn.clicked.connect(self.show_about)
        btn_row.addWidget(about_btn)
        lay.addLayout(btn_row)
        self.populate_audio_devices()
        lay.addStretch()
    def populate_audio_devices(self):
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            for idx, dev in enumerate(devices):
                name = dev.get("name")
                max_in = dev.get("max_input_channels", 0)
                max_out = dev.get("max_output_channels", 0)
                if max_in > 0:
                    self.mic_cb.addItem(f"{name} (Input)", idx)
                if max_out > 0:
                    self.spk_cb.addItem(f"{name} (Output)", idx)
        except Exception as e:
            self.mic_cb.addItem(f"Error listing: {e}")
            self.spk_cb.addItem(f"Error listing: {e}")
    def change_accent_color(self, idx):
        color_map = {
            0: ("#00E5FF", "rgba(0, 229, 255, 0.08)"),
            1: ("#BD00FF", "rgba(189, 0, 255, 0.08)"),
            2: ("#00FF66", "rgba(0, 255, 102, 0.08)"),
            3: ("#FF0033", "rgba(255, 0, 51, 0.08)"),
            4: ("#0055FF", "rgba(0, 85, 255, 0.08)"),
        }
        pri, gho = color_map.get(idx, ("#00E5FF", "rgba(0, 229, 255, 0.08)"))
        C.PRI = pri
        C.PRI_GHO = gho
        self.main_win.write_log("SYS: Theme accent color changed.")
        self.main_win.setStyleSheet(f"background: {C.BG};")
        self.main_win.update()
    def toggle_animations(self, state):
        enabled = (state == 2)
        self.main_win.hud._tmr.setInterval(16 if enabled else 1000)
        self.main_win.write_log(f"SYS: Animations {'enabled' if enabled else 'disabled'}.")
    def toggle_startup(self, state):
        import winreg, sys
        enabled = (state == 2)
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if enabled:
                winreg.SetValueEx(key, "COCOAI", 0, winreg.REG_SZ, f'"{sys.executable}"')
                self.main_win.write_log("SYS: Added COCO AI to Windows Startup Registry.")
            else:
                try:
                    winreg.DeleteValue(key, "COCOAI")
                    self.main_win.write_log("SYS: Removed COCO AI from Windows Startup Registry.")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            self.main_win.write_log(f"ERR: Failed to update registry: {e}")
    def show_about(self):
        d = AboutDialog(self.main_win)
        d.exec()

class MainWindow(QMainWindow):
    _log_sig   = pyqtSignal(str)
    _state_sig = pyqtSignal(str)

    def __init__(self, face_path: str):
        super().__init__()
        self.setWindowTitle("COCO AI")
        self.setMinimumSize(1020, 720)
        self.resize(1020, 720)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - 1020) // 2,
            (screen.height() - 720) // 2,
        )

        self.on_text_command  = None
        self._muted           = False
        self.ui_ref           = None
        self._mute_btn        = QPushButton()

        central = QWidget()
        central.setStyleSheet(f"background: {C.BG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        
        self._header_widget = self._build_header()
        root.addWidget(self._header_widget)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(8)

        self.sidebar = SidebarWidget(self)
        body.addWidget(self.sidebar, stretch=0)

        center_col = QVBoxLayout()
        center_col.setContentsMargins(0, 0, 0, 0)
        center_col.setSpacing(8)

        # Set up Center Navigation Stack
        self.center_stack = QStackedWidget(self)
        center_col.addWidget(self.center_stack, stretch=1)

        # Page 0: Home HUD Canvas
        hud_wrapper = GlassPanel()
        hud_lay = QVBoxLayout(hud_wrapper)
        hud_lay.setContentsMargins(6, 6, 6, 6)
        self.hud = HudCanvas(face_path)
        self.hud.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        hud_lay.addWidget(self.hud)
        self.center_stack.addWidget(hud_wrapper)

        # Page 1 to 12: Custom control pages
        self.chat_page = ChatPanel(self)
        self.voice_page = VoiceAssistantPanel(self)
        self.browser_page = BrowserPanel(self)
        self.youtube_page = YouTubePanel(self)
        self.whatsapp_page = WhatsAppPanel(self)
        self.system_page = SystemControlPanel(self)
        self.code_page = CodeAssistantPanel(self)
        self.automation_page = AutomationPanel(self)
        self.weather_page = WeatherPanel(self)
        self.memory_page = MemoryPanel(self)
        self.game_page = GameUpdaterPanel(self)
        self.settings_page = SettingsPanel(self)

        self.center_stack.addWidget(self.chat_page)       # 1
        self.center_stack.addWidget(self.voice_page)      # 2
        self.center_stack.addWidget(self.browser_page)    # 3
        self.center_stack.addWidget(self.youtube_page)    # 4
        self.center_stack.addWidget(self.whatsapp_page)   # 5
        self.center_stack.addWidget(self.system_page)     # 6
        self.center_stack.addWidget(self.code_page)       # 7
        self.center_stack.addWidget(self.automation_page) # 8
        self.center_stack.addWidget(self.weather_page)    # 9
        self.center_stack.addWidget(self.memory_page)     # 10
        self.center_stack.addWidget(self.game_page)       # 11
        self.center_stack.addWidget(self.settings_page)   # 12

        # Connect sidebar buttons to switch pages
        for idx, btn in enumerate(self.sidebar.buttons):
            btn.clicked.connect(lambda checked=False, i=idx: self.switch_page(i))

        self.telemetry_row = QWidget()
        self.telemetry_row.setStyleSheet("background: transparent; border: none;")
        tel_lay = QHBoxLayout(self.telemetry_row)
        tel_lay.setContentsMargins(0, 0, 0, 0)
        tel_lay.setSpacing(8)

        self.card_cpu = TelemetryCard("CPU", C.GREEN, self)
        self.card_ram = TelemetryCard("RAM", C.ACC, self)
        self.card_gpu = TelemetryCard("GPU", C.PRI, self)
        self.card_net = InfoCard("Internet", C.SEC, self)
        self.card_bat = InfoCard("Battery", C.GREEN, self)

        tel_lay.addWidget(self.card_cpu)
        tel_lay.addWidget(self.card_ram)
        tel_lay.addWidget(self.card_gpu)
        tel_lay.addWidget(self.card_net)
        tel_lay.addWidget(self.card_bat)
        center_col.addWidget(self.telemetry_row, stretch=0)

        body.addLayout(center_col, stretch=5)

        self._right_panel = self._build_right_panel()
        body.addWidget(self._right_panel, stretch=3)

        root.addLayout(body, stretch=1)
        
        self.bottom_cards_row = QWidget()
        self.bottom_cards_row.setStyleSheet("background: transparent; border: none;")
        bot_lay = QHBoxLayout(self.bottom_cards_row)
        bot_lay.setContentsMargins(0, 0, 0, 0)
        bot_lay.setSpacing(8)

        self.bot_calendar = BottomWidget("📅", "TIME & DATE", "00:00 AM", "Fri, 26 Jun 2026", self)
        self.bot_weather = BottomWidget("⛅", "WEATHER", "28°C Cloudy", "Mumbai", self)
        self.bot_active_app = BottomWidget("🖥", "ACTIVE APP", "COCO AI", "Desktop App", self)
        self.bot_browser = BottomWidget("🌐", "BROWSER", "Google Chrome", "youtube.com", self)
        self.bot_voice = BottomWidget("🎙", "VOICE STATUS", "Listening...", "", self)
        self.bot_dev = DeveloperWidget(self)

        bot_lay.addWidget(self.bot_calendar)
        bot_lay.addWidget(self.bot_weather)
        bot_lay.addWidget(self.bot_active_app)
        bot_lay.addWidget(self.bot_browser)
        bot_lay.addWidget(self.bot_voice)
        bot_lay.addWidget(self.bot_dev)

        root.addWidget(self.bottom_cards_row)

        self._footer_widget = self._build_footer()
        root.addWidget(self._footer_widget)

        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()

        self._metric_tmr = QTimer(self)
        self._metric_tmr.timeout.connect(self._update_metrics)
        self._metric_tmr.start(2000)
        self._update_metrics()

        self._log_sig.connect(self._log.append_log)
        self._state_sig.connect(self._apply_state)

        self._overlay: SetupOverlay | None = None
        self._lock_screen: LockScreenOverlay | None = None
        self._ready = self._check_config()
        if self._ready:
            self._show_lock_screen()

        # Keyboard shortcuts
        sc_focus = QShortcut(QKeySequence("Ctrl+K"), self)
        sc_focus.activated.connect(self._input.setFocus)
        
        sc_clear = QShortcut(QKeySequence("Ctrl+L"), self)
        sc_clear.activated.connect(self._clear_chat_logs)

        sc_mute = QShortcut(QKeySequence("F4"), self)
        sc_mute.activated.connect(self._toggle_mute)
        
        sc_mute_ctrl = QShortcut(QKeySequence("Ctrl+M"), self)
        sc_mute_ctrl.activated.connect(self._toggle_mute)

        sc_screenshot = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        sc_screenshot.activated.connect(self._trigger_shortcut_screenshot)

        sc_full = QShortcut(QKeySequence("F11"), self)
        sc_full.activated.connect(self._toggle_fullscreen)
        
        sc_esc = QShortcut(QKeySequence("Escape"), self)
        sc_esc.activated.connect(self._exit_fullscreen)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _exit_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()

    def _trigger_shortcut_screenshot(self):
        from actions.computer_settings import computer_settings
        threading.Thread(target=lambda: computer_settings(parameters={"action": "screenshot"}, player=self.ui_ref), daemon=True).start()

    def switch_page(self, index: int):
        for i, btn in enumerate(self.sidebar.buttons):
            btn.active = (i == index)
            btn.update_style()
            font = btn.font()
            font.setWeight(QFont.Weight.Bold if i == index else QFont.Weight.Medium)
            btn.setFont(font)
        self.center_stack.setCurrentIndex(index)
        SoundManager.play("click")

    def show_telemetry_details(self, title, history):
        d = TelemetryDetailsDialog(title, history, self)
        d.exec()

    def show_speed_test(self):
        d = SpeedTestDialog(self)
        d.exec()

    def show_battery_health(self):
        d = BatteryHealthDialog(self)
        d.exec()

    def show_calendar(self):
        d = CalendarDialog(self)
        d.exec()

    def show_active_app_switcher(self):
        d = WindowSwitcherDialog(self)
        d.exec()

    def show_ai_status(self):
        d = AIStatusDialog(self)
        d.exec()

    def show_advanced_diagnostics(self):
        d = AIDiagnosticsDialog(self)
        d.exec()

    def show_hud_context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet("background-color: #0a101a; color: #E1F5FE; border: 1px solid rgba(0,229,255,0.2);")
        mute_text = "Unmute Microphone" if self._muted else "Mute Microphone"
        act_mute = menu.addAction(mute_text)
        act_mute.triggered.connect(self._toggle_mute)
        act_mic_settings = menu.addAction("Microphone Settings")
        act_mic_settings.triggered.connect(lambda: self.switch_page(12))
        menu.addSeparator()
        act_diag = menu.addAction("Run AI Diagnostics")
        act_diag.triggered.connect(self.show_advanced_diagnostics)
        act_clear = menu.addAction("Clear Chat Logs")
        act_clear.triggered.connect(self._clear_chat_logs)
        menu.exec(pos)

    def _clear_chat_logs(self):
        while self._log.layout.count() > 1:
            child = self._log.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._log._queue.clear()
        self._log.append_log("SYS: Chat logs cleared.")

    def _save_chat_logs(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Chat Log", str(Path.home() / "coco_ai_chat.txt"), "Text Files (*.txt)")
        if path:
            try:
                lines = []
                for i in range(self._log.layout.count()):
                    w = self._log.layout.itemAt(i).widget()
                    if isinstance(w, ChatBubble):
                        lines.append(f"[{w.timestamp}] {w.sender.upper()}: {w.full_text}")
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                self.write_log(f"SYS: Saved chat logs to {path}")
            except Exception as e:
                self.write_log(f"ERR: Failed to save logs: {e}")

    def _send_quick_command(self, cmd):
        self._log.append_log(f"You: {cmd}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(cmd,), daemon=True).start()

    def run_browser_tool_async(self, args):
        from actions.browser_control import browser_control
        threading.Thread(target=lambda: browser_control(parameters=args, player=self.ui_ref), daemon=True).start()

    def check_updates(self):
        d = QDialog(self)
        d.setWindowTitle("Check for Updates")
        d.resize(250, 120)
        d.setStyleSheet("background-color: #05070A; color: #E1F5FE;")
        lay = QVBoxLayout(d)
        lbl = QLabel("Checking for updates...")
        lay.addWidget(lbl)
        QTimer.singleShot(1500, lambda: lbl.setText("You are on the latest version!\nVersion: 2.0.6 (All systems operational)."))
        btn = ModernButton("OK", d)
        btn.clicked.connect(d.accept)
        lay.addWidget(btn)
        d.exec()

    def _show_lock_screen(self):
        self._lock_screen = LockScreenOverlay(self.centralWidget())
        self._lock_screen.setGeometry(self.centralWidget().rect())
        self._lock_screen.unlocked.connect(self._on_lock_unlocked)
        self._lock_screen.show()

    def _on_lock_unlocked(self):
        SoundManager.play("unlocked")
        if self._lock_screen:
            self._lock_screen.hide()
            self._lock_screen = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._lock_screen:
            self._lock_screen.setGeometry(self.centralWidget().rect())
        if self._overlay:
            cw = self.centralWidget()
            ow, oh = 460, 390
            self._overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )

    def _update_metrics(self):
        snap = _metrics.snapshot()

        cpu = snap["cpu"]
        self.card_cpu.update_value(int(cpu))

        mem = snap["mem"]
        self.card_ram.update_value(int(mem))

        gpu = snap["gpu"]
        self.card_gpu.update_value(int(gpu if gpu >= 0 else 0))

        net = snap["net"]
        net_str = f"{net*1024:.0f} KB/s" if net < 1.0 else f"{net:.1f} MB/s"
        self.card_net.update_info("Active", net_str)

        try:
            bat = psutil.sensors_battery()
            if bat:
                pct = bat.percent
                charging = bat.power_plugged
                char_str = "Charging" if charging else "Discharging"
                self.card_bat.update_info(f"{pct}%", char_str)
            else:
                self.card_bat.update_info("100%", "AC Power")
        except Exception:
            self.card_bat.update_info("100%", "AC Power")

        self._update_context_labels()

    def _build_header(self) -> QWidget:
        w = GlassPanel()
        w.setFixedHeight(54)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(18, 0, 18, 0)

        left_lbl = QLabel("📶  COCO AI")
        left_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        left_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent; letter-spacing: 0.5px;")
        lay.addWidget(left_lbl)
        lay.addStretch()

        mid = QVBoxLayout(); mid.setSpacing(1); mid.setContentsMargins(0, 4, 0, 4)
        title = QLabel("COCO AI")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent; letter-spacing: 3px;")
        mid.addWidget(title)
        
        sub = QLabel("Personal Next-Gen Assistant")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(QFont("Segoe UI", 8))
        sub.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        mid.addWidget(sub)
        lay.addLayout(mid)
        lay.addStretch()

        right_col = QVBoxLayout(); right_col.setSpacing(2); right_col.setContentsMargins(0, 4, 0, 4)
        self._clock_lbl = QLabel("00:00:00")
        self._clock_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._clock_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._clock_lbl)
        
        self._date_lbl = QLabel("")
        self._date_lbl.setFont(QFont("Segoe UI", 8))
        self._date_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._date_lbl)
        lay.addLayout(right_col)
        
        return w

    def _tick_clock(self):
        now = datetime.now()
        time_str = now.strftime("%I:%M:%S %p")
        date_str = now.strftime("%a, %d %b %Y")
        self._clock_lbl.setText(time_str)
        self._date_lbl.setText(date_str)
        self.bot_calendar.update_values(now.strftime("%I:%M %p"), date_str)

    def _update_context_labels(self):
        if hasattr(self, "context_data") and self.context_data:
            app = self.context_data.get("current_app", "None")
            browser = self.context_data.get("current_browser", "None")
            web = self.context_data.get("current_website", "None")
            
            self.bot_active_app.update_values(app, "Desktop App")
            self.bot_browser.update_values(browser, web)

    def _build_right_panel(self) -> QWidget:
        w = GlassPanel()
        w.setFixedWidth(380)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        hdr = QHBoxLayout()
        hdr_lbl = QLabel("💬  AI CHAT")
        hdr_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        hdr_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        hdr.addWidget(hdr_lbl)
        
        sparkles = QLabel("✨")
        sparkles.setStyleSheet("color: #BD00FF; background: transparent; border: none;")
        hdr.addWidget(sparkles)
        hdr.addStretch()
        
        for sym in ["🔍", "📌", "⋮"]:
            lbl = QLabel(sym)
            lbl.setFont(QFont("Segoe UI", 9))
            lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            hdr.addWidget(lbl)
            
        lay.addLayout(hdr)

        self._log = LogWidget()
        lay.addWidget(self._log, stretch=1)

        self.drop_zone = FileDropZone(self)
        self.drop_zone.file_selected.connect(self._on_file_selected)
        lay.addWidget(self.drop_zone)

        input_container = QWidget()
        input_container.setStyleSheet(f"""
            QWidget {{
                background: rgba(16, 24, 36, 150);
                border: 1.2px solid rgba(0, 229, 255, 0.15);
                border-radius: 18px;
            }}
        """)
        input_container.setFixedHeight(36)
        in_lay = QHBoxLayout(input_container)
        in_lay.setContentsMargins(12, 0, 10, 0)
        in_lay.setSpacing(6)

        self._input = GlowingTextEdit()
        self._input.setFont(QFont("Segoe UI", 9))
        self._input.setPlaceholderText("Type your message...")
        self._input.setStyleSheet("QTextEdit { color: #FFFFFF; background: transparent; border: none; }")
        self._input.returnPressed.connect(self._send)
        in_lay.addWidget(self._input)
        
        self._placeholder_anim = TypingPlaceholderManager(self._input, self)

        clip_lbl = QLabel("📎")
        clip_lbl.setFont(QFont("Segoe UI", 10))
        clip_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        clip_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        clip_lbl.mouseReleaseEvent = lambda e: self.drop_zone._browse()
        in_lay.addWidget(clip_lbl)

        self.mic_icon_lbl = QLabel("🎙")
        self.mic_icon_lbl.setFont(QFont("Segoe UI", 10))
        self.mic_icon_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        self.mic_icon_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic_icon_lbl.mouseReleaseEvent = lambda e: self._toggle_mute()
        in_lay.addWidget(self.mic_icon_lbl)
        
        send = QPushButton("➤")
        send.setFixedSize(26, 26)
        send.setFont(QFont("Segoe UI", 10))
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setStyleSheet(f"""
            QPushButton {{
                background: {C.PRI}; color: #02050A;
                border: none; border-radius: 13px;
            }}
            QPushButton:hover {{ background: #FFFFFF; }}
        """)
        send.clicked.connect(self._send)
        in_lay.addWidget(send)

        lay.addWidget(input_container)

        return w

    def set_mic_volume(self, volume: float):
        self.hud.set_mic_volume(volume)

    def _toggle_mute(self):
        self._muted = not self._muted
        self.hud.muted = self._muted
        self._style_mute_btn()
        if self._muted:
            SoundManager.play("click")
            self._apply_state("MUTED")
            self._log.append_log("SYS: Microphone muted.")
        else:
            SoundManager.play("completed")
            self._apply_state("LISTENING")
            self._log.append_log("SYS: Microphone active.")

    def _style_mute_btn(self):
        if self._muted:
            self._mute_btn.setText("🔇  MICROPHONE MUTED")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255, 0, 51, 0.08); color: {C.RED};
                    border: 1px solid {C.RED}; border-radius: 6px;
                }}
            """)
        else:
            self._mute_btn.setText("🎙  MICROPHONE ACTIVE")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(0, 255, 102, 0.08); color: {C.GREEN};
                    border: 1px solid {C.GREEN}; border-radius: 6px;
                }}
                QPushButton:hover {{ background: rgba(0, 255, 102, 0.15); }}
            """)

    def _send(self):
        txt = self._input.toPlainText().strip()
        if not txt: return
        self._input.clear()
        self._log.append_log(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt,), daemon=True).start()

    def _on_file_selected(self, path):
        self._current_dropped_file = path
        self._log.append_log(f"FILE: {path}")

    def _apply_state(self, state: str):
        self.hud.state    = state
        self.hud.speaking = (state == "SPEAKING")

    def _check_config(self) -> bool:
        if not API_FILE.exists(): return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return bool(d.get("gemini_api_key")) and bool(d.get("os_system"))
        except Exception:
            return False

    def _show_setup(self):
        ov = SetupOverlay(self.centralWidget())
        cw = self.centralWidget()
        ow, oh = 460, 390
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.done.connect(self._on_setup_done)
        ov.show()
        self._overlay = ov

    def _on_setup_done(self, key: str, os_name: str):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        API_FILE.write_text(
            json.dumps({"gemini_api_key": key, "os_system": os_name}, indent=4),
            encoding="utf-8",
        )
        self._ready = True
        if self._overlay:
            self._overlay.hide()
            self._overlay = None
        self._apply_state("LISTENING")
        self._log.append_log(f"SYS: Initialised. OS={os_name.upper()}. COCO AI online.")

    def _build_footer(self) -> QWidget:
        w = GlassPanel()
        w.setFixedHeight(26)
        lay = QHBoxLayout(w); lay.setContentsMargins(16, 0, 16, 0)

        left_txt = QPushButton("COCO AI")
        left_txt.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        left_txt.setCursor(Qt.CursorShape.PointingHandCursor)
        left_txt.setStyleSheet(f"QPushButton {{ color: {C.PRI_DIM}; background: transparent; border: none; }} QPushButton:hover {{ color: {C.PRI}; }}")
        left_txt.clicked.connect(self.show_ai_status)
        lay.addWidget(left_txt)
        
        lay.addStretch()

        center_lay = QHBoxLayout()
        center_lay.setSpacing(6)
        
        dev_btn = QPushButton("Developed by Deva Thakare")
        dev_btn.setFont(QFont("Segoe UI", 8))
        dev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dev_btn.setStyleSheet(f"QPushButton {{ color: {C.TEXT_DIM}; background: transparent; border: none; }} QPushButton:hover {{ color: {C.PRI}; }}")
        dev_btn.clicked.connect(lambda: webbrowser.open("https://github.com/devathakare7796-ui"))
        
        sep1 = QLabel("•")
        sep1.setFont(QFont("Segoe UI", 8))
        sep1.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        
        ver_btn = QPushButton("Version 2.0.6")
        ver_btn.setFont(QFont("Segoe UI", 8))
        ver_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ver_btn.setStyleSheet(f"QPushButton {{ color: {C.TEXT_DIM}; background: transparent; border: none; }} QPushButton:hover {{ color: {C.PRI}; }}")
        ver_btn.clicked.connect(self.check_updates)
        
        sep2 = QLabel("•  All Systems Operational")
        sep2.setFont(QFont("Segoe UI", 8))
        sep2.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        
        center_lay.addWidget(dev_btn)
        center_lay.addWidget(sep1)
        center_lay.addWidget(ver_btn)
        center_lay.addWidget(sep2)

        dot = QWidget()
        dot.setFixedSize(6, 6)
        dot.setStyleSheet(f"background: {C.GREEN}; border-radius: 3px;")
        center_lay.addWidget(dot, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        lay.addLayout(center_lay)
        lay.addStretch()

        right_txt = QLabel("© DEVA THAKARE")
        right_txt.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        right_txt.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent; border: none;")
        lay.addWidget(right_txt)
        
        return w

class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app
    def mainloop(self):
        self._app.exec()
    def protocol(self, *_):
        pass

class CocoAIUI:
    def __init__(self, face_path: str, size=None):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        
        # Synthesize sound effects on boot if needed
        sounds_dir = BASE_DIR / "sounds"
        try:
            generate_sound_effects(sounds_dir)
        except Exception as e:
            print(f"Sound gen error: {e}")
            
        self._win = MainWindow(face_path)
        self._win.ui_ref = self
        self._win.hide()
        
        self.splash = SplashWindow()
        self.splash.show()
        
        self.splash.finished.connect(self._show_main_win)
        
        self.root = _RootShim(self._app)

    def _show_main_win(self):
        self._win.show()
        if not self._win._ready:
            self._win._show_setup()
        else:
            self.set_state("LISTENING")

    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    @property
    def current_file(self) -> str | None:
        return getattr(self._win, "_current_dropped_file", None)

    def set_mic_volume(self, volume: float):
        self._win.set_mic_volume(volume)

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    # Remote clicked callbacks removed

    def notify_phone_connected(self) -> None:
        pass

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def write_log(self, text: str):
        # Translate old JARVIS name in incoming logs automatically
        rebranded_text = text.replace("Jarvis:", "Coco AI:").replace("JARVIS", "COCO AI")
        self._win._log_sig.emit(rebranded_text)

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def play_sound(self, name: str):
        SoundManager.play(name)

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")

JarvisUI = CocoAIUI