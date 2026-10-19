#!/usr/bin/env python3
# IceWM / X11 cursor magnifier with a notification-area icon and RGB/CMYK readout.
# Requires: PySide6 and pynput. Intended for X11 sessions (such as IceWM).
# Install pynput in the same Python environment used to run this script:
#   python3 -m pip install --user pynput
#
# Global shortcut and initial zoom can be changed in ~/.config/icewm-magnifier/config.json
# or through the small settings dialog (right-click the magnifier).

import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QRect, QObject, Signal
from PySide6.QtGui import QColor, QGuiApplication, QCursor, QPainter, QPen, QPixmap, QFont, QAction, QIcon
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QHBoxLayout, QVBoxLayout,
    QDialog, QFormLayout, QLineEdit, QSpinBox, QPushButton,
    QDialogButtonBox, QMessageBox, QStyle, QSystemTrayIcon, QMenu, QComboBox, QCheckBox, QTabWidget, QGroupBox
)

try:
    from pynput import keyboard
except ImportError:
    print("ERROR: the pynput module is missing. Install it with: python3 -m pip install --user pynput", file=sys.stderr)
    sys.exit(1)

try:
    from Xlib import X, XK, display as xdisplay
except ImportError:
    print("ERROR: the python-xlib module is missing. Install it with: python3 -m pip install --user python-xlib", file=sys.stderr)
    sys.exit(1)


APP_DIR = Path.home() / ".config" / "icewm-magnifier"
CONFIG_FILE = APP_DIR / "config.json"
DEFAULTS = {
    "hotkey": "<ctrl>+<alt>+m",
    "window_width": 520,
    "window_height": 360,
    "zoom": 2.0,
    "max_zoom": 20.0,
    "follow_cursor": True,
    "show_crosshair": True,
    "show_pixel_scale": True,
    "copy_mode": "magnified_area"
}



def make_app_icon():
    """Draw a small native pixmap icon; avoids oversized SVG theme-icon warnings."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(QColor("#263238"), 2))
    painter.setBrush(QColor("#69d2ff"))
    painter.drawEllipse(4, 4, 19, 19)
    painter.setPen(QPen(QColor("#263238"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawLine(20, 20, 28, 28)
    painter.end()
    return QIcon(pixmap)


def load_config():
    config = DEFAULTS.copy()
    try:
        if CONFIG_FILE.exists():
            user_config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            config.update({k: v for k, v in user_config.items() if k in DEFAULTS})
            config["max_zoom"] = min(20.0, max(2.0, float(config.get("max_zoom", 20.0))))
            config["zoom"] = min(float(config.get("zoom", 2.0)), config["max_zoom"])
    except Exception as exc:
        print(f"Could not load settings: {exc}", file=sys.stderr)
    return config


def save_config(config):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rgb_to_cmyk(r, g, b):
    """Return normalized CMYK values in the 0..1 range, suitable for LaTeX xcolor."""
    rr, gg, bb = r / 255.0, g / 255.0, b / 255.0
    k = 1.0 - max(rr, gg, bb)
    if k >= 1.0 - 1e-12:
        return 0.0, 0.0, 0.0, 1.0
    c = (1.0 - rr - k) / (1.0 - k)
    m = (1.0 - gg - k) / (1.0 - k)
    y = (1.0 - bb - k) / (1.0 - k)
    return tuple(max(0.0, min(1.0, v)) for v in (c, m, y, k))


class HotkeyBridge(QObject):
    activated = Signal()
    hide_magnifier = Signal()
    copy_requested = Signal()


class SettingsDialog(QDialog):
    settings_applied = Signal(dict)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cursor Magnifier Preferences")
        self.setModal(True)
        self.resize(500, 390)

        self.tabs = QTabWidget()

        # Tab 1: Magnifier
        magnifier_tab = QWidget()
        magnifier_form = QFormLayout(magnifier_tab)
        self.width_box = QSpinBox()
        self.width_box.setRange(180, 1600)
        self.width_box.setValue(int(config["window_width"]))
        self.height_box = QSpinBox()
        self.height_box.setRange(140, 1200)
        self.height_box.setValue(int(config["window_height"]))
        self.zoom_box = QSpinBox()
        self.zoom_box.setRange(2, 20)
        self.zoom_box.setValue(min(20, max(2, int(float(config["zoom"])))) )
        self.max_zoom_box = QSpinBox()
        self.max_zoom_box.setRange(2, 20)
        self.max_zoom_box.setValue(min(20, max(2, int(float(config.get("max_zoom", 20.0))))))
        self.zoom_box.setMaximum(self.max_zoom_box.value())
        self.max_zoom_box.valueChanged.connect(self._maximum_zoom_changed)
        magnifier_form.addRow("Window width (px):", self.width_box)
        magnifier_form.addRow("Window height (px):", self.height_box)
        magnifier_form.addRow("Initial zoom:", self.zoom_box)
        magnifier_form.addRow("Maximum zoom:", self.max_zoom_box)
        zoom_note = QLabel("The maximum magnification is limited to 20×.")
        zoom_note.setWordWrap(True)
        magnifier_form.addRow(zoom_note)
        self.tabs.addTab(magnifier_tab, "Magnifier")

        # Tab 2: Display
        display_tab = QWidget()
        display_layout = QVBoxLayout(display_tab)
        display_group = QGroupBox("Magnifier overlay")
        display_group_layout = QVBoxLayout(display_group)
        self.pixel_scale_box = QCheckBox("Show pixel scale and px coordinates")
        self.pixel_scale_box.setChecked(bool(config.get("show_pixel_scale", True)))
        self.crosshair_box = QCheckBox("Show center crosshair")
        self.crosshair_box.setChecked(bool(config.get("show_crosshair", True)))
        self.follow_cursor_box = QCheckBox("Follow mouse cursor")
        self.follow_cursor_box.setChecked(bool(config.get("follow_cursor", True)))
        display_group_layout.addWidget(self.pixel_scale_box)
        display_group_layout.addWidget(self.crosshair_box)
        display_group_layout.addWidget(self.follow_cursor_box)
        display_layout.addWidget(display_group)
        display_layout.addStretch(1)
        self.tabs.addTab(display_tab, "Display")

        # Tab 3: Color & Copy
        color_tab = QWidget()
        color_layout = QVBoxLayout(color_tab)
        color_group = QGroupBox("Copy with C while the magnifier is visible")
        color_form = QFormLayout(color_group)
        self.copy_mode_box = QComboBox()
        self.copy_modes = [
            ("rgb_values", "RGB values: R=100, G=12, B=86"),
            ("latex_cmyk", "LaTeX xcolor — CMYK"),
            ("latex_rgb", "LaTeX xcolor — RGB"),
            ("magnified_area", "Magnified area (image)"),
        ]
        for key, label in self.copy_modes:
            self.copy_mode_box.addItem(label, key)
        current_index = self.copy_mode_box.findData(config.get("copy_mode", "magnified_area"))
        self.copy_mode_box.setCurrentIndex(max(0, current_index))
        color_form.addRow("Copy format:", self.copy_mode_box)
        color_note = QLabel("The status area displays RGB, CMYK percentages and a one-line LaTeX xcolor definition.")
        color_note.setWordWrap(True)
        color_layout.addWidget(color_group)
        color_layout.addWidget(color_note)
        color_layout.addStretch(1)
        self.tabs.addTab(color_tab, "Color & Copy")

        # Tab 4: Shortcuts
        shortcuts_tab = QWidget()
        shortcuts_form = QFormLayout(shortcuts_tab)
        self.hotkey = QLineEdit(str(config["hotkey"]))
        shortcuts_form.addRow("Global toggle hotkey:", self.hotkey)
        shortcuts_form.addRow("Show / hide:", QLabel("Ctrl + Alt + M (default)"))
        shortcuts_form.addRow("Copy selected data:", QLabel("C (while magnifier is visible)"))
        shortcuts_form.addRow("Hide magnifier:", QLabel("Esc"))
        shortcuts_form.addRow("Reset zoom:", QLabel("Middle-click the magnifier"))
        shortcut_note = QLabel("Restart the application after changing the global hotkey.")
        shortcut_note.setWordWrap(True)
        shortcuts_form.addRow(shortcut_note)
        self.tabs.addTab(shortcuts_tab, "Shortcuts")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.RestoreDefaults |
            QDialogButtonBox.StandardButton.Apply |
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.apply_button = buttons.button(QDialogButtonBox.StandardButton.Apply)
        self.apply_button.clicked.connect(self._apply_preview)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self._restore_defaults)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(buttons)

    def _maximum_zoom_changed(self, value):
        self.zoom_box.setMaximum(value)
        if self.zoom_box.value() > value:
            self.zoom_box.setValue(value)

    def _apply_preview(self):
        # Apply settings immediately while keeping Preferences open.
        self.settings_applied.emit(self.values())

    def _restore_defaults(self):
        defaults = DEFAULTS
        self.hotkey.setText(str(defaults["hotkey"]))
        self.width_box.setValue(int(defaults["window_width"]))
        self.height_box.setValue(int(defaults["window_height"]))
        self.max_zoom_box.setValue(20)
        self.zoom_box.setValue(int(defaults["zoom"]))
        self.pixel_scale_box.setChecked(bool(defaults["show_pixel_scale"]))
        self.crosshair_box.setChecked(bool(defaults["show_crosshair"]))
        self.follow_cursor_box.setChecked(bool(defaults["follow_cursor"]))
        idx = self.copy_mode_box.findData(defaults["copy_mode"])
        self.copy_mode_box.setCurrentIndex(max(0, idx))

    def values(self):
        maximum = min(20, max(2, self.max_zoom_box.value()))
        return {
            "hotkey": self.hotkey.text().strip(),
            "window_width": self.width_box.value(),
            "window_height": self.height_box.value(),
            "zoom": float(min(self.zoom_box.value(), maximum)),
            "max_zoom": float(maximum),
            "follow_cursor": self.follow_cursor_box.isChecked(),
            "show_crosshair": self.crosshair_box.isChecked(),
            "show_pixel_scale": self.pixel_scale_box.isChecked(),
            "copy_mode": str(self.copy_mode_box.currentData()),
        }


class GlobalWheelCapture(QObject):
    """Grab X11 wheel buttons and the C key while the magnifier is visible."""
    scrolled = Signal(int)
    copy_pressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.display = xdisplay.Display()
        self.root = self.display.screen().root
        self.active = False
        self.copy_keycode = self.display.keysym_to_keycode(XK.XK_c)
        self.timer = QTimer(self)
        self.timer.setInterval(10)
        self.timer.timeout.connect(self.poll)

    def enable(self):
        if self.active:
            return
        try:
            for button in (4, 5):
                self.root.grab_button(
                    button, X.AnyModifier, False, X.ButtonPressMask,
                    X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE
                )
            # Consume C while magnifier is visible, so it copies without typing into the app underneath.
            self.root.grab_key(
                self.copy_keycode, X.AnyModifier, False,
                X.GrabModeAsync, X.GrabModeAsync
            )
            self.display.sync()
            self.active = True
            self.timer.start()
        except Exception as exc:
            try:
                self.root.ungrab_button(X.AnyButton, X.AnyModifier)
                self.root.ungrab_key(self.copy_keycode, X.AnyModifier)
                self.display.sync()
            except Exception:
                pass
            raise RuntimeError(
                "Could not capture the mouse wheel globally. "
                "Make sure the application is running under X11 and no other application "
                "has already grabbed the wheel events."
            ) from exc

    def disable(self):
        self.timer.stop()
        if not self.active:
            return
        try:
            self.root.ungrab_button(X.AnyButton, X.AnyModifier)
            self.root.ungrab_key(self.copy_keycode, X.AnyModifier)
            self.display.sync()
        finally:
            self.active = False

    def poll(self):
        try:
            while self.display.pending_events():
                event = self.display.next_event()
                if event.type == X.ButtonPress:
                    if event.detail == 4:
                        self.scrolled.emit(1)
                    elif event.detail == 5:
                        self.scrolled.emit(-1)
                elif event.type == X.KeyPress and event.detail == self.copy_keycode:
                    self.copy_pressed.emit()
        except Exception as exc:
            print(f"Mouse-wheel monitoring error: {exc}", file=sys.stderr)
            self.disable()

    def close(self):
        self.disable()
        try:
            self.display.close()
        except Exception:
            pass


class Magnifier(QWidget):
    def __init__(self, config, wheel_capture):
        super().__init__(None, Qt.WindowType.Tool |
                         Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.config = config
        self.wheel_capture = wheel_capture
        self.wheel_capture.scrolled.connect(self.change_zoom)
        self.wheel_capture.copy_pressed.connect(self.copy_current_selection)
        self.zoom = float(config["zoom"])
        self.max_zoom = min(20.0, float(config["max_zoom"]))
        self.view_width = int(config["window_width"])
        self.view_height = int(config["window_height"])
        self.status_height = 72
        self.setFixedSize(self.view_width, self.view_height)
        self.setMouseTracking(True)
        self.setWindowTitle("Cursor Magnifier")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.image = QPixmap()
        self.rgb = (0, 0, 0)
        self.cursor_pos = None
        self._screen = QGuiApplication.primaryScreen()

        self.timer = QTimer(self)
        self.timer.setInterval(45)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()

    def toggle(self):
        if self.isVisible():
            self.hide()
            self.wheel_capture.disable()
        else:
            self.zoom = float(self.config["zoom"])
            self.show()
            self.refresh()
            self.raise_()
            try:
                self.wheel_capture.enable()
            except RuntimeError as exc:
                self.hide()
                QMessageBox.critical(None, "Egérgörgő-hiba", str(exc))

    def refresh(self):
        if not self.isVisible():
            return
        pos = QCursor.pos()
        self.cursor_pos = pos
        screens = QGuiApplication.screens()
        screen = next((s for s in screens if s.geometry().contains(pos)), self._screen)
        if screen is None:
            return

        geom = screen.geometry()
        # QScreen.grabWindow(0, ...) captures from the desktop/root window on X11.
        # Capture a source area smaller than the display window, then scale it up.
        source_w = max(1, int((self.view_width - 2) / self.zoom))
        source_h = max(1, int((self.view_height - self.status_height - 2) / self.zoom))
        sx = pos.x() - source_w // 2
        sy = pos.y() - source_h // 2

        # Keep the source rectangle inside the selected screen.
        sx = max(geom.left(), min(sx, geom.right() - source_w + 1))
        sy = max(geom.top(), min(sy, geom.bottom() - source_h + 1))

        # QScreen grab coordinates are local to that screen's geometry.
        self.image = screen.grabWindow(
            0, sx - geom.left(), sy - geom.top(), source_w, source_h
        )
        if not self.image.isNull():
            center_x = max(0, min(pos.x() - sx, self.image.width() - 1))
            center_y = max(0, min(pos.y() - sy, self.image.height() - 1))
            pixel = self.image.toImage().pixelColor(center_x, center_y)
            self.rgb = (pixel.red(), pixel.green(), pixel.blue())

        if self.config.get("follow_cursor", True):
            self.position_near_cursor(pos, source_w, source_h, geom)
        self.update()

    def position_near_cursor(self, pos, source_w, source_h, screen_geom):
        # Keep the magnifier outside the sampled source area to avoid feedback.
        gap = 12
        x = pos.x() + source_w // 2 + gap
        if x + self.width() > screen_geom.right() + 1:
            x = pos.x() - source_w // 2 - gap - self.width()
        y = pos.y() - self.height() // 2
        x = max(screen_geom.left(), min(x, screen_geom.right() - self.width() + 1))
        y = max(screen_geom.top(), min(y, screen_geom.bottom() - self.height() + 1))
        self.move(x, y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        view_rect = QRect(1, 1, self.view_width - 2, self.view_height - self.status_height - 2)
        painter.fillRect(self.rect(), QColor(24, 24, 24))
        if not self.image.isNull():
            painter.drawPixmap(view_rect, self.image)

            # Pixel ruler: origin (0, 0) is the bottom-left corner of the image viewport.
            # Source-image pixels are enlarged by approximately self.zoom display pixels.
            if self.config.get("show_pixel_scale", True):
                left = view_rect.left()
                right = view_rect.right()
                top = view_rect.top()
                bottom = view_rect.bottom()
                ruler_bg = QColor(12, 18, 24, 210)
                painter.fillRect(QRect(left, bottom - 19, view_rect.width(), 19), ruler_bg)
                painter.fillRect(QRect(left, top, 34, view_rect.height()), ruler_bg)
                painter.setFont(QFont("monospace", 7))
                painter.setPen(QPen(QColor(110, 235, 255, 230), 1))

                # Horizontal x-axis along the bottom. Tick every 5 source px; label every 10 px.
                source_width = max(1, self.image.width())
                source_height = max(1, self.image.height())
                tick_px = 5
                for px in range(0, source_width + 1, tick_px):
                    x = left + round(px * view_rect.width() / source_width)
                    if x > right:
                        break
                    painter.drawLine(x, bottom - 19, x, bottom - (13 if px % 10 == 0 else 16))
                    if px % 10 == 0:
                        painter.drawText(
                            x + 2, bottom - 5, f"{px} px"
                        )

                # Vertical y-axis along the left. Origin is bottom-left; y increases upwards.
                for px in range(0, source_height + 1, tick_px):
                    y_pos = bottom - round(px * view_rect.height() / source_height)
                    if y_pos < top:
                        break
                    painter.drawLine(left + 28, y_pos, left + (21 if px % 10 == 0 else 25), y_pos)
                    if px % 10 == 0 and px > 0:
                        painter.drawText(
                            left + 2, y_pos - 2, f"{px}"
                        )
                painter.setPen(QPen(QColor(255, 220, 100, 230), 1))
                painter.drawText(left + 2, bottom - 22, "0,0")
                painter.setPen(QPen(QColor(110, 235, 255, 230), 1))

            if self.config.get("show_crosshair", True):
                cx, cy = view_rect.center().x(), view_rect.center().y()
                painter.setPen(QPen(QColor(255, 40, 40, 220), 1))
                painter.drawLine(cx - 12, cy, cx + 12, cy)
                painter.drawLine(cx, cy - 12, cx, cy + 12)
                painter.setPen(QPen(QColor(255, 255, 255, 220), 1))
                painter.drawRect(cx - 2, cy - 2, 4, 4)

        r, g, b = self.rgb
        c, m, y, k = rgb_to_cmyk(r, g, b)
        status_top = self.view_height - self.status_height - 1
        painter.fillRect(1, status_top, self.view_width - 2, self.status_height, QColor(30, 30, 30))
        painter.setPen(QPen(QColor(70, 70, 70), 1))
        painter.drawLine(1, status_top, self.view_width - 2, status_top)

        # Row 1: color swatch, RGB and zoom.
        swatch = QRect(9, status_top + 7, 30, 18)
        painter.fillRect(swatch, QColor(r, g, b))
        painter.setPen(QPen(QColor(210, 210, 210), 1))
        painter.drawRect(swatch)
        painter.setPen(QColor(245, 245, 245))
        painter.setFont(QFont("monospace", 9, QFont.Weight.Bold))
        painter.drawText(48, status_top + 21, f"RGB  {r:3d}, {g:3d}, {b:3d}")
        painter.setPen(QColor(120, 215, 255))
        painter.drawText(self.view_width - 62, status_top + 21, f"{self.zoom:.1f}×")

        # Row 2: CMYK percentages, matching the RGB typography.
        painter.setPen(QColor(225, 225, 225))
        painter.setFont(QFont("monospace", 9, QFont.Weight.Bold))
        painter.drawText(48, status_top + 40,
                         f"CMYK  {round(c*100):3d}%, {round(m*100):3d}%, {round(y*100):3d}%, {round(k*100):3d}%")

        # Row 3: one single-line LaTeX xcolor readout.
        latex_text = f"\\definecolor{{pixel}}{{cmyk}}{{{c:.3f},{m:.3f},{y:.3f},{k:.3f}}}"
        label_x = 9
        latex_y = status_top + 61
        painter.setPen(QColor(255, 205, 110))
        painter.setFont(QFont("Sans Serif", 8, QFont.Weight.Bold))
        label = "LaTeX · xcolor:"
        painter.drawText(label_x, latex_y, label)
        label_width = painter.fontMetrics().horizontalAdvance(label) + 8
        code_font = QFont("monospace", 8)
        painter.setFont(code_font)
        painter.setPen(QColor(205, 225, 235))
        available = self.view_width - label_x - label_width - 8
        code_width = painter.fontMetrics().horizontalAdvance(latex_text)
        if code_width > available:
            code_font.setPointSize(7)
            painter.setFont(code_font)
        painter.drawText(label_x + label_width, latex_y, latex_text)
        painter.setPen(QPen(QColor(180, 180, 180), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def copy_current_selection(self):
        """Copy the selected color representation or the enlarged screen crop."""
        mode = self.config.get("copy_mode", "magnified_area")
        r, g, b = self.rgb
        c, m, y, k = rgb_to_cmyk(r, g, b)
        clipboard = QGuiApplication.clipboard()

        if mode == "magnified_area":
            if self.image.isNull():
                return
            target = self.image.scaled(
                max(1, self.view_width - 2),
                max(1, self.view_height - self.status_height - 2),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            clipboard.setPixmap(target)
            print("Clipboard: magnified image area")
        elif mode == "latex_cmyk":
            text = (
                r"\definecolor{pixel}{cmyk}"
                f"{{{c:.3f},{m:.3f},{y:.3f},{k:.3f}}}"
            )
            clipboard.setText(text)
            print("Clipboard:", text)
        elif mode == "latex_rgb":
            text = r"\definecolor{pixel}{RGB}" + f"{{{r},{g},{b}}}"
            clipboard.setText(text)
            print("Clipboard:", text)
        else:
            text = f"R={r}, G={g}, B={b}"
            clipboard.setText(text)
            print("Clipboard:", text)

    def change_zoom(self, steps):
        if not steps:
            return
        self.zoom = max(2.0, min(self.max_zoom, self.zoom * (1.25 ** steps)))
        self.refresh()

    def wheelEvent(self, event):
        # Fallback for wheel events that happen directly over the magnifier.
        delta = event.angleDelta().y()
        steps = (1 if delta > 0 else -1) if delta else 0
        self.change_zoom(steps)
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.wheel_capture.disable()
            event.accept()
        else:
            super().keyPressEvent(event)

    def hide_from_escape(self):
        if self.isVisible():
            self.hide()
            self.wheel_capture.disable()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.open_settings()
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.zoom = float(self.config["zoom"])
            self.refresh()
        else:
            super().mousePressEvent(event)

    def open_settings(self):
        dialog = SettingsDialog(self.config, self)
        dialog.settings_applied.connect(self.apply_settings)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.apply_settings(dialog.values())

    def apply_settings(self, new_config):
        # Preserve future options already present in config.
        self.config.update(new_config)
        self.view_width = int(self.config["window_width"])
        self.view_height = int(self.config["window_height"])
        self.zoom = min(float(self.config["zoom"]), float(self.config["max_zoom"]))
        self.max_zoom = min(20.0, float(self.config["max_zoom"]))
        self.setFixedSize(self.view_width, self.view_height)
        self.update()
        try:
            save_config(self.config)
        except Exception as exc:
            QMessageBox.warning(self, "Save error", str(exc))



class ControllerWindow(QWidget):
    """A normal taskbar-visible control window that remains available when the magnifier is hidden."""
    def __init__(self, magnifier, config):
        super().__init__(None, Qt.WindowType.Window)
        self.magnifier = magnifier
        self.config = config
        self.setWindowTitle("Cursor Magnifier")
        self.setMinimumWidth(340)
        self.setWindowFlags(Qt.WindowType.Window |
                            Qt.WindowType.WindowMinimizeButtonHint |
                            Qt.WindowType.WindowCloseButtonHint)
        self.setWindowIcon(make_app_icon())

        title = QLabel("Cursor Magnifier")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        description = QLabel(
            "The control window stays on the IceWM/Xfce taskbar. "
            "Esc hides the magnifier only."
        )
        description.setWordWrap(True)

        self.status = QLabel("Status: magnifier hidden")
        self.show_button = QPushButton("Show magnifier")
        self.preferences_button = QPushButton("Preferences…")
        self.minimize_button = QPushButton("Minimize to taskbar")
        self.exit_button = QPushButton("Exit")

        self.show_button.clicked.connect(self.toggle_magnifier)
        self.preferences_button.clicked.connect(self.magnifier.open_settings)
        self.minimize_button.clicked.connect(self.showMinimized)
        self.exit_button.clicked.connect(QApplication.instance().quit)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(8)
        layout.addWidget(self.status)
        layout.addWidget(self.show_button)
        layout.addWidget(self.preferences_button)
        layout.addWidget(self.minimize_button)
        layout.addWidget(self.exit_button)

        self.status_timer = QTimer(self)
        self.status_timer.setInterval(250)
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start()

    def toggle_magnifier(self):
        self.magnifier.toggle()
        self.update_status()

    def update_status(self):
        visible = self.magnifier.isVisible()
        self.status.setText("Status: magnifier active" if visible else "Status: magnifier hidden")
        self.show_button.setText("Hide magnifier" if visible else "Show magnifier")

    def closeEvent(self, event):
        # Closing the controller minimizes it instead of quitting; use the explicit Exit button to quit.
        event.ignore()
        self.showMinimized()



class TrayController(QObject):
    """System-tray controller; avoids creating a regular taskbar window."""
    def __init__(self, magnifier, config, app):
        super().__init__()
        self.magnifier = magnifier
        self.config = config
        self.app = app

        self.icon = QSystemTrayIcon(make_app_icon(), self)
        self.icon.setToolTip("Cursor Magnifier — hidden")

        self.menu = QMenu()
        self.toggle_action = QAction("Show magnifier", self.menu)
        self.toggle_action.triggered.connect(self.toggle_magnifier)
        self.menu.addAction(self.toggle_action)

        preferences_action = QAction("Preferences…", self.menu)
        preferences_action.triggered.connect(self.magnifier.open_settings)
        self.menu.addAction(preferences_action)

        self.menu.addSeparator()
        quit_action = QAction("Exit", self.menu)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)

        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self.on_activated)

        self.status_timer = QTimer(self)
        self.status_timer.setInterval(300)
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start()

        self.icon.show()
        self.update_status()

    def toggle_magnifier(self):
        self.magnifier.toggle()
        self.update_status()

    def on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_magnifier()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_magnifier()

    def update_status(self):
        visible = self.magnifier.isVisible()
        self.toggle_action.setText("Hide magnifier" if visible else "Show magnifier")
        self.icon.setToolTip("Cursor Magnifier — active" if visible else "Cursor Magnifier — hidden")

    def hide(self):
        self.icon.hide()


def main():
    if sys.platform != "linux":
        print("This version is designed for Linux/X11.", file=sys.stderr)
        return 2
    if not (Path("/tmp/.X11-unix").exists() and
            (not __import__("os").environ.get("WAYLAND_DISPLAY"))):
        print("Warning: this application is designed for X11; screen capture and hotkeys may be limited under Wayland.",
              file=sys.stderr)

    app = QApplication(sys.argv)
    app.setApplicationName("IceWM Cursor Magnifier")
    app.setQuitOnLastWindowClosed(False)
    config = load_config()
    try:
        wheel_capture = GlobalWheelCapture()
    except Exception as exc:
        QMessageBox.critical(None, "X11 error", f"Could not connect to X11:\n{exc}")
        return 1
    magnifier = Magnifier(config, wheel_capture)
    app.aboutToQuit.connect(wheel_capture.close)

    bridge = HotkeyBridge()
    bridge.activated.connect(magnifier.toggle)
    bridge.hide_magnifier.connect(magnifier.hide_from_escape)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(
            None, "No system tray available",
            "The system does not report an available system tray. "
            "Under IceWM/Xfce, check whether a system-tray applet is running."
        )
        wheel_capture.close()
        return 1

    tray = TrayController(magnifier, config, app)
    app.aboutToQuit.connect(tray.hide)

    def on_hotkey():
        # pynput runs in a background thread; emit a Qt signal to update the GUI safely.
        bridge.activated.emit()

    def on_escape():
        # A global Escape handler is required because the frameless magnifier deliberately has no focus.
        bridge.hide_magnifier.emit()

    try:
        hotkeys = keyboard.GlobalHotKeys({
            str(config["hotkey"]): on_hotkey,
            "<esc>": on_escape,
        })
        hotkeys.start()
    except Exception as exc:
        QMessageBox.critical(
            None, "Gyorsbillentyű-hiba",
            f"Could not register the global hotkey or Esc:\n"
            f"{config['hotkey']}\n\n{exc}"
        )
        return 1

    # The tray icon stays in the notification area while the magnifier is hidden.
    exit_code = app.exec()
    hotkeys.stop()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
