from datetime import datetime
import hashlib
import json
import math
import os
import re
import struct
import sys
import time
import wave
import winsound

import keyboard
import pyperclip
from PyQt6.QtCore import (
    QEasingCurve,
    QObject,
    QPoint,
    QPropertyAnimation,
    QTimer,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QIcon,
    QImage,
    QPainter,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

# ================= SETTINGS =================
HOTKEY = "alt+v"
HISTORY_FILE = "evertail_history.json"
SETTINGS_FILE = "evertail_settings.json"
IMAGES_DIR = "copied_images"
SOUNDS_DIR = "sounds"
COPY_SOUND_PATH = os.path.join(SOUNDS_DIR, "copy_soft.wav")
PASTE_SOUND_PATH = os.path.join(SOUNDS_DIR, "paste_soft.wav")
MAX_ITEMS = 150

TRANSLATIONS = {
    "en": {
        "search_placeholder": "🔍 Search text and links...",
        "tab_all": "All",
        "tab_text": "Text",
        "tab_link": "Links",
        "tab_image": "Images",
        "tab_pinned": "📌",
        "clear_btn": "Clear",
        "status_bar": (
            "Click on a card to copy it to clipboard (then press Ctrl+V)"
        ),
        "empty_list": "Empty ✨\nCopy any text, link, or take a screenshot",
        "badge_text": "📝 TEXT",
        "badge_link": "🔗 LINK",
        "badge_image": "🖼 IMAGE",
        "settings_title": "Settings",
        "sound_label": "Sound Feedback",
        "sound_on": "🔊 On",
        "sound_off": "🔇 Off",
        "lang_label": "Language",
        "tray_open": f"Open ({HOTKEY.upper()})",
        "tray_sound": "Sound Feedback",
        "tray_clear": "Clear Unpinned",
        "tray_quit": "Quit",
    },
    "ru": {
        "search_placeholder": "🔍 Поиск по тексту и ссылкам...",
        "tab_all": "Все",
        "tab_text": "Текст",
        "tab_link": "Ссылки",
        "tab_image": "Скрины",
        "tab_pinned": "📌",
        "clear_btn": "Очистить",
        "status_bar": (
            "Клик по карточке копирует её в буфер обмена (вставка — Ctrl+V)"
        ),
        "empty_list": (
            "Пусто ✨\nСкопируй любой текст, ссылку или сделай скриншот"
        ),
        "badge_text": "📝 ТЕКСТ",
        "badge_link": "🔗 ССЫЛКА",
        "badge_image": "🖼 СКРИНШОТ",
        "settings_title": "Настройки",
        "sound_label": "Звуковой отклик",
        "sound_on": "🔊 Вкл",
        "sound_off": "🔇 Выкл",
        "lang_label": "Язык",
        "tray_open": f"Открыть ({HOTKEY.upper()})",
        "tray_sound": "Звуковой отклик",
        "tray_clear": "Очистить незакрепленные",
        "tray_quit": "Выход",
    },
}


def ensure_soft_sounds():
    """Generates lightweight, pleasant sound effects locally."""
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    sample_rate = 44100

    if not os.path.exists(COPY_SOUND_PATH):
        duration = 0.055
        n_samples = int(sample_rate * duration)
        with wave.open(COPY_SOUND_PATH, "w") as wav_file:
            wav_file.setparams(
                (1, 2, sample_rate, n_samples, "NONE", "not compressed")
            )
            for i in range(n_samples):
                t = i / sample_rate
                progress = i / n_samples
                freq = 440 + (240 * (progress**0.7))
                envelope = math.sin(math.pi * progress) * math.exp(
                    -3.5 * progress
                )
                sample = 0.14 * envelope * math.sin(2 * math.pi * freq * t)
                wav_file.writeframes(struct.pack("<h", int(sample * 32767)))

    if not os.path.exists(PASTE_SOUND_PATH):
        duration = 0.040
        n_samples = int(sample_rate * duration)
        with wave.open(PASTE_SOUND_PATH, "w") as wav_file:
            wav_file.setparams(
                (1, 2, sample_rate, n_samples, "NONE", "not compressed")
            )
            for i in range(n_samples):
                t = i / sample_rate
                progress = i / n_samples
                freq = 580 - (220 * progress)
                envelope = math.sin(math.pi * progress) * math.exp(
                    -4.5 * progress
                )
                sample = 0.11 * envelope * math.sin(2 * math.pi * freq * t)
                wav_file.writeframes(struct.pack("<h", int(sample * 32767)))


class HotkeyBridge(QObject):
    toggle_signal = pyqtSignal()


class AnimatedCard(QFrame):
    clicked = pyqtSignal(dict)
    pin_toggled = pyqtSignal(dict)
    delete_clicked = pyqtSignal(dict)

    def __init__(self, item: dict, lang: str = "en", parent=None):
        super().__init__(parent)
        self.item = item
        self.lang = lang
        t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("ClipCard")
        self.setStyleSheet(self._get_style(hovered=False))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        badge_info = {
            "text": (t["badge_text"], "#a29bfe"),
            "link": (t["badge_link"], "#00d2ff"),
            "image": (t["badge_image"], "#2ed573"),
        }
        badge_text, badge_color = badge_info.get(
            item["type"], (t["badge_text"], "#a29bfe")
        )

        badge_lbl = QLabel(f"{badge_text}  •  {item['time']}")
        badge_lbl.setStyleSheet(
            f"color: {badge_color}; font-size: 11px; font-weight: 700;"
            " background: transparent;"
        )
        top_row.addWidget(badge_lbl)
        top_row.addStretch()

        pin_btn = QPushButton("📌")
        pin_active = item.get("pinned", False)
        pin_btn.setFixedSize(26, 24)
        pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pin_btn.setStyleSheet(f"""
            QPushButton {{
                background: {'rgba(255, 165, 2, 0.22)' if pin_active else 'transparent'};
                border: 1px solid {'#ffa502' if pin_active else 'transparent'};
                border-radius: 6px;
                font-size: 12px;
            }}
            QPushButton:hover {{ background: rgba(255, 255, 255, 0.12); }}
        """)
        pin_btn.clicked.connect(lambda: self.pin_toggled.emit(self.item))
        top_row.addWidget(pin_btn)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(26, 24)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #747d8c;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(255, 71, 87, 0.25);
                color: #ff4757;
            }
        """)
        del_btn.clicked.connect(lambda: self.delete_clicked.emit(self.item))
        top_row.addWidget(del_btn)

        layout.addLayout(top_row)

        if item["type"] == "image" and os.path.exists(item["content"]):
            img_lbl = QLabel()
            img_lbl.setStyleSheet("background: transparent; border-radius: 8px;")
            pix = QPixmap(item["content"])
            if not pix.isNull():
                scaled = pix.scaled(
                    360,
                    130,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                img_lbl.setPixmap(scaled)
            layout.addWidget(img_lbl)
        else:
            preview = item["content"].strip().replace("\n", " ↵ ")
            if len(preview) > 160:
                preview = preview[:160] + "..."

            text_color = "#00d2ff" if item["type"] == "link" else "#f1f2f6"
            content_lbl = QLabel(preview)
            content_lbl.setWordWrap(True)
            content_lbl.setStyleSheet(
                f"color: {text_color}; font-size: 13px; background:"
                " transparent; line-height: 1.35;"
            )
            layout.addWidget(content_lbl)

    def _get_style(self, hovered: bool, clicked_flash: bool = False) -> str:
        if clicked_flash:
            return """
                QFrame#ClipCard {
                    background-color: rgba(46, 213, 115, 0.28);
                    border: 1px solid #2ed573;
                    border-radius: 12px;
                }
            """
        if hovered:
            return """
                QFrame#ClipCard {
                    background-color: #26293a;
                    border: 1px solid #6c5ce7;
                    border-radius: 12px;
                }
            """
        border_col = "#ffa502" if self.item.get("pinned") else "#2a2d3e"
        return f"""
            QFrame#ClipCard {{
                background-color: #1c1e2b;
                border: 1px solid {border_col};
                border-radius: 12px;
            }}
        """

    def enterEvent(self, event):
        self.setStyleSheet(self._get_style(hovered=True))
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(self._get_style(hovered=False))
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setStyleSheet(
                self._get_style(hovered=False, clicked_flash=True)
            )
            QTimer.singleShot(120, lambda: self.clicked.emit(self.item))
        super().mousePressEvent(event)


class EverTail(QWidget):

    def __init__(self):
        super().__init__()
        os.makedirs(IMAGES_DIR, exist_ok=True)
        ensure_soft_sounds()

        self.history = []
        self.sound_enabled = True
        self.lang = "en"
        self.last_pos = None
        self.current_filter = "all"
        self.last_text = ""
        self.last_img_hash = ""
        self.drag_pos = None
        self.ignore_next_clip = False

        self.load_settings()
        self.load_history()
        self.init_window()
        self.init_ui()
        self.init_animations()
        self.init_tray()
        self.init_clipboard_and_hotkeys()
        self.apply_language()
        self.render_list()

    def t(self, key: str) -> str:
        return TRANSLATIONS.get(self.lang, TRANSLATIONS["en"]).get(key, key)

    def play_sfx(self, sound_path: str):
        if self.sound_enabled and os.path.exists(sound_path):
            try:
                winsound.PlaySound(
                    sound_path,
                    winsound.SND_FILENAME
                    | winsound.SND_ASYNC
                    | winsound.SND_NODEFAULT,
                )
            except Exception:
                pass

    def init_window(self):
        self.setWindowTitle("EverTail")
        self.resize(450, 620)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        screen = QApplication.primaryScreen().availableGeometry()
        if self.last_pos and len(self.last_pos) == 2:
            x = min(
                max(self.last_pos[0], screen.left() + 10),
                screen.right() - self.width() - 10,
            )
            y = min(
                max(self.last_pos[1], screen.top() + 10),
                screen.bottom() - self.height() - 10,
            )
            self.move(x, y)
        else:
            x = screen.center().x() - self.width() // 2
            y = screen.center().y() - self.height() // 2
            self.move(x, y)
            self.last_pos = [x, y]

    def init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(14, 14, 14, 14)

        self.container = QFrame()
        self.container.setObjectName("MainContainer")
        self.container.setStyleSheet("""
            QFrame#MainContainer {
                background-color: #12131c;
                border: 1px solid #2d3146;
                border-radius: 18px;
            }
            QScrollBar:vertical {
                background: #12131c;
                width: 6px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: #3a3f5c;
                border-radius: 3px;
                min-height: 25px;
            }
            QScrollBar::handle:vertical:hover {
                background: #6c5ce7;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 190))
        shadow.setOffset(0, 6)
        self.container.setGraphicsEffect(shadow)
        outer_layout.addWidget(self.container)

        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(10)

        # 1. Header
        header = QHBoxLayout()
        self.title_lbl = QLabel("EverTail")
        self.title_lbl.setStyleSheet(
            "color: #ffffff; font-size: 17px; font-weight: 800;"
        )
        header.addWidget(self.title_lbl)
        header.addStretch()

        badge = QLabel(HOTKEY.upper())
        badge.setStyleSheet("""
            background: rgba(108, 92, 231, 0.2);
            color: #a29bfe;
            border: 1px solid #6c5ce7;
            border-radius: 6px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: bold;
        """)
        header.addWidget(badge)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(28, 28)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self.toggle_settings_panel)
        header.addWidget(self.settings_btn)
        self.update_settings_btn_style(False)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #1e2030;
                color: #a4b0be;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #ff4757;
                color: white;
            }
        """)
        close_btn.clicked.connect(self.animate_hide)
        header.addWidget(close_btn)
        main_layout.addLayout(header)

        # 1.5 Settings Panel (Collapsible)
        self.settings_panel = QFrame()
        self.settings_panel.setObjectName("SettingsPanel")
        self.settings_panel.setStyleSheet("""
            QFrame#SettingsPanel {
                background-color: #1c1e2b;
                border: 1px solid #2a2d3e;
                border-radius: 12px;
            }
        """)
        self.settings_panel.setVisible(False)
        settings_layout = QVBoxLayout(self.settings_panel)
        settings_layout.setContentsMargins(12, 10, 12, 10)
        settings_layout.setSpacing(8)

        # Sound setting row
        sound_row = QHBoxLayout()
        self.sound_setting_lbl = QLabel()
        self.sound_setting_lbl.setStyleSheet(
            "color: #f1f2f6; font-size: 13px; font-weight: 600;"
        )
        sound_row.addWidget(self.sound_setting_lbl)
        sound_row.addStretch()

        self.sound_toggle_btn = QPushButton()
        self.sound_toggle_btn.setFixedSize(85, 26)
        self.sound_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sound_toggle_btn.clicked.connect(self.toggle_sound)
        sound_row.addWidget(self.sound_toggle_btn)
        settings_layout.addLayout(sound_row)

        # Language setting row
        lang_row = QHBoxLayout()
        self.lang_setting_lbl = QLabel()
        self.lang_setting_lbl.setStyleSheet(
            "color: #f1f2f6; font-size: 13px; font-weight: 600;"
        )
        lang_row.addWidget(self.lang_setting_lbl)
        lang_row.addStretch()

        self.lang_en_btn = QPushButton("English")
        self.lang_en_btn.setFixedSize(70, 26)
        self.lang_en_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lang_en_btn.clicked.connect(lambda: self.set_language("en"))

        self.lang_ru_btn = QPushButton("Русский")
        self.lang_ru_btn.setFixedSize(70, 26)
        self.lang_ru_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lang_ru_btn.clicked.connect(lambda: self.set_language("ru"))

        lang_row.addWidget(self.lang_en_btn)
        lang_row.addWidget(self.lang_ru_btn)
        settings_layout.addLayout(lang_row)

        main_layout.addWidget(self.settings_panel)

        # 2. Search
        self.search_input = QLineEdit()
        self.search_input.textChanged.connect(self.render_list)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #1c1e2b;
                color: #f1f2f6;
                border: 1px solid #2a2d3e;
                border-radius: 10px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #6c5ce7;
                background-color: #212434;
            }
        """)
        main_layout.addWidget(self.search_input)

        # 3. Filter Tabs
        tabs_layout = QHBoxLayout()
        tabs_layout.setSpacing(6)
        self.tab_buttons = {}
        tab_keys = ["all", "text", "link", "image", "pinned"]
        for key in tab_keys:
            btn = QPushButton()
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self.set_filter(k))
            self.tab_buttons[key] = btn
            tabs_layout.addWidget(btn)

        tabs_layout.addStretch()

        self.clear_btn = QPushButton()
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 71, 87, 0.14);
                color: #ff6b81;
                border: 1px solid rgba(255, 71, 87, 0.3);
                border-radius: 8px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #ff4757;
                color: white;
            }
        """)
        self.clear_btn.clicked.connect(self.clear_unpinned)
        tabs_layout.addWidget(self.clear_btn)
        main_layout.addLayout(tabs_layout)
        self.update_tab_styles()

        # 4. Card List
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        self.list_container = QWidget()
        self.list_container.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 2, 4, 2)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch()

        self.scroll.setWidget(self.list_container)
        main_layout.addWidget(self.scroll)

        # 5. Status Bar
        self.status_lbl = QLabel()
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet("color: #57606f; font-size: 11px;")
        main_layout.addWidget(self.status_lbl)

    def update_settings_btn_style(self, active: bool):
        self.settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: {'#6c5ce7' if active else '#1e2030'};
                color: {'#ffffff' if active else '#a4b0be'};
                border: 1px solid {'#8275f0' if active else '#2a2d3e'};
                border-radius: 8px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: {'#6c5ce7' if active else '#282b3f'};
                color: white;
            }}
        """)

    def toggle_settings_panel(self):
        visible = not self.settings_panel.isVisible()
        self.settings_panel.setVisible(visible)
        self.update_settings_btn_style(visible)

    def update_settings_ui(self):
        if self.sound_enabled:
            self.sound_toggle_btn.setText(self.t("sound_on"))
            self.sound_toggle_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(46, 213, 115, 0.16);
                    color: #2ed573;
                    border: 1px solid rgba(46, 213, 115, 0.4);
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover { background: rgba(46, 213, 115, 0.28); }
            """)
        else:
            self.sound_toggle_btn.setText(self.t("sound_off"))
            self.sound_toggle_btn.setStyleSheet("""
                QPushButton {
                    background: #12131c;
                    color: #747d8c;
                    border: 1px solid #2a2d3e;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover { background: #282b3f; color: #f1f2f6; }
            """)

        for code, btn in [("en", self.lang_en_btn), ("ru", self.lang_ru_btn)]:
            active = self.lang == code
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {'#6c5ce7' if active else '#12131c'};
                    color: {'#ffffff' if active else '#a4b0be'};
                    border: 1px solid {'#8275f0' if active else '#2a2d3e'};
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: {'#6c5ce7' if active else '#272a3d'};
                    color: #ffffff;
                }}
            """)

        if hasattr(self, "tray_sound_action"):
            self.tray_sound_action.setChecked(self.sound_enabled)

    def set_language(self, lang: str):
        if self.lang != lang:
            self.lang = lang
            self.save_settings()
            self.apply_language()
            self.render_list()

    def apply_language(self):
        self.search_input.setPlaceholderText(self.t("search_placeholder"))
        self.tab_buttons["all"].setText(self.t("tab_all"))
        self.tab_buttons["text"].setText(self.t("tab_text"))
        self.tab_buttons["link"].setText(self.t("tab_link"))
        self.tab_buttons["image"].setText(self.t("tab_image"))
        self.tab_buttons["pinned"].setText(self.t("tab_pinned"))
        self.clear_btn.setText(self.t("clear_btn"))
        self.status_lbl.setText(self.t("status_bar"))

        self.sound_setting_lbl.setText(self.t("sound_label"))
        self.lang_setting_lbl.setText(self.t("lang_label"))
        self.settings_btn.setToolTip(self.t("settings_title"))

        if hasattr(self, "tray_open_action"):
            self.tray_open_action.setText(self.t("tray_open"))
            self.tray_sound_action.setText(self.t("tray_sound"))
            self.tray_clear_action.setText(self.t("tray_clear"))
            self.tray_quit_action.setText(self.t("tray_quit"))

        self.update_settings_ui()

    def toggle_sound(self):
        self.sound_enabled = not self.sound_enabled
        self.update_settings_ui()
        self.save_settings()
        if self.sound_enabled:
            self.play_sfx(COPY_SOUND_PATH)

    def init_animations(self):
        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setDuration(180)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def animate_show(self):
        screen = QApplication.primaryScreen().availableGeometry()
        if self.last_pos and len(self.last_pos) == 2:
            target_x = min(
                max(self.last_pos[0], screen.left() + 10),
                screen.right() - self.width() - 10,
            )
            target_y = min(
                max(self.last_pos[1], screen.top() + 10),
                screen.bottom() - self.height() - 10,
            )
        else:
            target_x = screen.center().x() - self.width() // 2
            target_y = screen.center().y() - self.height() // 2
            self.last_pos = [target_x, target_y]

        self.move(target_x, target_y)
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self.search_input.setFocus()

        self.fade_anim.stop()
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.start()

    def animate_hide(self):
        if not self.isVisible():
            return
        self.last_pos = [self.pos().x(), self.pos().y()]
        self.save_settings()

        self.fade_anim.stop()
        self.fade_anim.setStartValue(self.windowOpacity())
        self.fade_anim.setEndValue(0.0)

        def on_finished():
            if self.windowOpacity() == 0.0:
                self.hide()

        try:
            self.fade_anim.finished.disconnect()
        except TypeError:
            pass
        self.fade_anim.finished.connect(on_finished)
        self.fade_anim.start()

    def toggle_window(self):
        if self.isVisible() and self.windowOpacity() > 0.1:
            self.animate_hide()
        else:
            self.render_list()
            self.animate_show()

    def update_tab_styles(self):
        for key, btn in self.tab_buttons.items():
            active = key == self.current_filter
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {'#6c5ce7' if active else '#1c1e2b'};
                    color: {'#ffffff' if active else '#a4b0be'};
                    border: 1px solid {'#8275f0' if active else '#2a2d3e'};
                    border-radius: 8px;
                    padding: 5px 10px;
                    font-size: 11px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: {'#6c5ce7' if active else '#272a3d'};
                    color: #ffffff;
                }}
            """)

    def set_filter(self, filter_key: str):
        self.current_filter = filter_key
        self.update_tab_styles()
        self.render_list()

    def init_clipboard_and_hotkeys(self):
        self.qt_clipboard = QApplication.clipboard()
        mime = self.qt_clipboard.mimeData()
        if mime and mime.hasText():
            self.last_text = mime.text()

        self.qt_clipboard.dataChanged.connect(self.on_clipboard_change)

        self.hotkey_bridge = HotkeyBridge()
        self.hotkey_bridge.toggle_signal.connect(self.toggle_window)
        keyboard.add_hotkey(
            HOTKEY, lambda: self.hotkey_bridge.toggle_signal.emit()
        )

    def is_url(self, text: str) -> bool:
        return bool(
            re.match(r"^(https?://|www\.)\S+$", text.strip(), re.IGNORECASE)
        )

    def on_clipboard_change(self):
        if self.ignore_next_clip:
            self.ignore_next_clip = False
            return

        mime = self.qt_clipboard.mimeData()
        if mime is None:
            return

        if mime.hasImage():
            qimg = self.qt_clipboard.image()
            if not qimg.isNull():
                ptr = qimg.bits()
                ptr.setsize(qimg.sizeInBytes())
                img_hash = hashlib.md5(bytes(ptr)).hexdigest()
                if img_hash != self.last_img_hash:
                    self.last_img_hash = img_hash
                    filename = os.path.join(
                        IMAGES_DIR, f"clip_{int(time.time() * 1000)}.png"
                    )
                    qimg.save(filename, "PNG")
                    self.add_item("image", filename)
                    self.play_sfx(COPY_SOUND_PATH)
                return

        if mime.hasText():
            text = mime.text()
            if text and text.strip() and text != self.last_text:
                self.last_text = text
                item_type = "link" if self.is_url(text) else "text"
                self.add_item(item_type, text)
                self.play_sfx(COPY_SOUND_PATH)

    def add_item(self, item_type: str, content: str):
        for existing in self.history:
            if (
                existing["type"] == item_type
                and existing["content"] == content
            ):
                self.history.remove(existing)
                existing["time"] = datetime.now().strftime("%H:%M:%S")
                self.history.insert(0, existing)
                self.save_history()
                self.render_list()
                return

        new_item = {
            "id": int(time.time() * 1000),
            "type": item_type,
            "content": content,
            "time": datetime.now().strftime("%H:%M:%S"),
            "pinned": False,
        }
        self.history.insert(0, new_item)

        if len(self.history) > MAX_ITEMS:
            for i in range(len(self.history) - 1, -1, -1):
                if not self.history[i].get("pinned"):
                    removed = self.history.pop(i)
                    if removed["type"] == "image" and os.path.exists(
                        removed["content"]
                    ):
                        try:
                            os.remove(removed["content"])
                        except OSError:
                            pass
                    break

        self.save_history()
        self.render_list()

    def render_list(self):
        while self.list_layout.count() > 1:
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        query = self.search_input.text().strip().lower()
        filtered = []

        for item in self.history:
            if self.current_filter == "pinned" and not item.get("pinned"):
                continue
            elif (
                self.current_filter not in ("all", "pinned")
                and item["type"] != self.current_filter
            ):
                continue

            if query and item["type"] != "image":
                if query not in item["content"].lower():
                    continue
            filtered.append(item)

        if not filtered:
            empty = QLabel(self.t("empty_list"))
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                "color: #57606f; font-size: 13px; padding: 50px 10px;"
            )
            self.list_layout.insertWidget(0, empty)
            return

        for idx, item in enumerate(filtered):
            card = AnimatedCard(item, lang=self.lang)
            card.clicked.connect(self.copy_item_to_clipboard)
            card.pin_toggled.connect(self.toggle_pin)
            card.delete_clicked.connect(self.delete_item)
            self.list_layout.insertWidget(idx, card)

    def copy_item_to_clipboard(self, item: dict):
        """Copies item to system clipboard without keystroke emulation."""
        self.ignore_next_clip = True
        if item["type"] == "image":
            if os.path.exists(item["content"]):
                img = QImage(item["content"])
                self.qt_clipboard.setImage(img)
        else:
            self.last_text = item["content"]
            pyperclip.copy(item["content"])

        self.play_sfx(PASTE_SOUND_PATH)
        self.animate_hide()

    def toggle_pin(self, item: dict):
        item["pinned"] = not item.get("pinned", False)
        self.save_history()
        self.render_list()

    def delete_item(self, item: dict):
        if item in self.history:
            self.history.remove(item)
            if item["type"] == "image" and os.path.exists(item["content"]):
                try:
                    os.remove(item["content"])
                except OSError:
                    pass
            self.save_history()
            self.render_list()

    def clear_unpinned(self):
        kept = []
        for item in self.history:
            if item.get("pinned"):
                kept.append(item)
            elif item["type"] == "image" and os.path.exists(item["content"]):
                try:
                    os.remove(item["content"])
                except OSError:
                    pass
        self.history = kept
        self.save_history()
        self.render_list()

    def save_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    self.history = json.load(f)
            except Exception:
                self.history = []

    def save_settings(self):
        try:
            data = {
                "sound_enabled": self.sound_enabled,
                "lang": self.lang,
                "last_pos": self.last_pos,
            }
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.sound_enabled = data.get("sound_enabled", True)
                    self.lang = data.get("lang", "en")
                    self.last_pos = data.get("last_pos", None)
            except Exception:
                self.sound_enabled = True
                self.lang = "en"
                self.last_pos = None

    def create_app_icon(self) -> QIcon:
        pix = QPixmap(64, 64)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor("#6c5ce7")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(4, 4, 56, 56, 16, 16)
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawRoundedRect(18, 16, 28, 34, 5, 5)
        painter.setBrush(QBrush(QColor("#12131c")))
        painter.drawRoundedRect(24, 12, 16, 8, 3, 3)
        painter.end()
        return QIcon(pix)

    def init_tray(self):
        icon = self.create_app_icon()
        self.setWindowIcon(icon)

        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip(f"EverTail ({HOTKEY.upper()})")

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background-color: #1c1e2b; color: #f1f2f6; border: 1px solid #2a2d3e; padding: 6px; }
            QMenu::item { padding: 6px 20px; border-radius: 4px; }
            QMenu::item:selected { background-color: #6c5ce7; }
        """)

        self.tray_open_action = QAction(self.t("tray_open"), self)
        self.tray_open_action.triggered.connect(self.animate_show)
        menu.addAction(self.tray_open_action)

        self.tray_sound_action = QAction(self.t("tray_sound"), self)
        self.tray_sound_action.setCheckable(True)
        self.tray_sound_action.setChecked(self.sound_enabled)
        self.tray_sound_action.triggered.connect(self.toggle_sound)
        menu.addAction(self.tray_sound_action)

        self.tray_clear_action = QAction(self.t("tray_clear"), self)
        self.tray_clear_action.triggered.connect(self.clear_unpinned)
        menu.addAction(self.tray_clear_action)

        menu.addSeparator()

        self.tray_quit_action = QAction(self.t("tray_quit"), self)
        self.tray_quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(self.tray_quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self.toggle_window()
            if reason == QSystemTrayIcon.ActivationReason.Trigger
            else None
        )
        self.tray.show()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event):
        if (
            event.buttons() == Qt.MouseButton.LeftButton
            and self.drag_pos is not None
        ):
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = None
            self.last_pos = [self.pos().x(), self.pos().y()]
            self.save_settings()
            event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = EverTail()
    window.animate_show()
    sys.exit(app.exec())