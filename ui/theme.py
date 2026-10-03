"""Shared light and dark application themes."""

from __future__ import annotations


_PALETTES = {
    "light": {
        "window": "#f3f6fb",
        "surface": "#ffffff",
        "surface_alt": "#f8fafd",
        "surface_hover": "#eaf0f7",
        "border": "#d9e2ef",
        "text": "#1d2939",
        "muted": "#66758a",
        "accent": "#3478f6",
        "accent_hover": "#2465dc",
        "accent_soft": "#e4edff",
        "input": "#ffffff",
        "selection": "#dce8ff",
        "danger": "#b93838",
    },
    "dark": {
        "window": "#111821",
        "surface": "#17212d",
        "surface_alt": "#1d2937",
        "surface_hover": "#263747",
        "border": "#344456",
        "text": "#edf3fa",
        "muted": "#a1b0c2",
        "accent": "#5794ff",
        "accent_hover": "#78a8ff",
        "accent_soft": "#24375a",
        "input": "#121b25",
        "selection": "#24375a",
        "danger": "#ff7777",
    },
}


def application_stylesheet(theme: str) -> str:
    """Return the application-wide stylesheet for ``light`` or ``dark``."""
    try:
        colors = _PALETTES[theme]
    except KeyError as exc:
        raise ValueError(f"Unsupported theme: {theme!r}") from exc

    return f"""
        QWidget {{
            color: {colors['text']};
            font-family: 'Segoe UI';
            font-size: 13px;
        }}
        QMainWindow, QWidget#AppShell, QWidget#HomePage, QWidget#ContentPage,
        QWidget#TaskPanel, QWidget#VoicePanel, QWidget#DashboardWidget {{
            background-color: {colors['window']};
        }}
        QWidget#DashboardWidget {{
            border: 1px solid {colors['border']};
            border-radius: 14px;
        }}
        QLabel#DashboardBrand {{ font-size: 17px; font-weight: 750; }}
        QLabel#DashboardGreeting {{ color: {colors['muted']}; font-size: 14px; padding: 4px 1px; }}
        QLabel#DashboardSection {{ color: {colors['accent']}; font-size: 13px; font-weight: 750; }}
        QLabel#DashboardStatus {{ color: {colors['muted']}; font-size: 11px; }}
        QWidget#DashboardWidget QPushButton {{ padding: 7px 9px; }}
        QWidget#DashboardWidget QComboBox {{ padding: 7px 6px; }}
        QWidget#DashboardWidget QLineEdit {{ padding: 9px; }}
        QWidget#DashboardWidget QListWidget {{ border-radius: 10px; }}
        QWidget#DashboardWidget QListWidget::item {{ padding: 8px; margin: 2px; }}
        QWidget#Sidebar {{
            background-color: {colors['surface']};
            border-right: 1px solid {colors['border']};
        }}
        QWidget#SidebarSeparator {{ background-color: {colors['border']}; }}
        QLabel#SidebarLabel {{ color: {colors['muted']}; font-size: 11px; font-weight: 700; }}
        QLabel#BrandMark {{
            color: #ffffff;
            background-color: {colors['accent']};
            border-radius: 12px;
            font-size: 17px;
            font-weight: 800;
            min-width: 42px;
            max-width: 42px;
            min-height: 42px;
            max-height: 42px;
            qproperty-alignment: AlignCenter;
        }}
        QLabel#BrandTitle {{ font-size: 17px; font-weight: 700; }}
        QLabel#TaskHeading {{ font-size: 21px; font-weight: 700; }}
        QLabel#PageHeading {{ font-size: 27px; font-weight: 700; }}
        QLabel#Greeting {{ color: {colors['accent']}; font-size: 31px; font-weight: 800; }}
        QLabel#WelcomeLine {{ color: {colors['muted']}; font-size: 19px; }}
        QLabel#CardHeading {{ font-size: 16px; font-weight: 700; padding-bottom: 5px; }}
        QLabel#PanelStatus {{ color: {colors['accent']}; }}
        QLabel#BrandSubtitle, QLabel#Description, QLabel#Footer {{ color: {colors['muted']}; }}
        QLabel#SectionEyebrow {{
            color: {colors['accent']};
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1px;
        }}
        QLabel#Heading {{ font-size: 27px; font-weight: 700; padding-bottom: 2px; }}
        QLabel#MatchNotice {{
            color: {colors['muted']};
            background-color: {colors['surface_alt']};
            border: 1px solid {colors['border']};
            border-radius: 9px;
            padding: 10px 13px;
        }}
        QLabel#Footer {{ font-size: 11px; padding-top: 2px; }}
        QLineEdit, QTextEdit, QDateEdit, QTimeEdit, QComboBox {{
            color: {colors['text']};
            background-color: {colors['input']};
            border: 1px solid {colors['border']};
            border-radius: 8px;
            padding: 9px 11px;
            selection-background-color: {colors['accent']};
        }}
        QLineEdit:focus, QTextEdit:focus, QDateEdit:focus, QTimeEdit:focus, QComboBox:focus {{
            border: 1px solid {colors['accent']};
        }}
        QLineEdit#SearchInput {{
            border-radius: 12px;
            padding: 15px 17px;
            font-size: 16px;
        }}
        QPushButton {{
            color: {colors['text']};
            background-color: {colors['surface_alt']};
            border: 1px solid {colors['border']};
            border-radius: 8px;
            padding: 9px 14px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {colors['surface_hover']};
            border-color: {colors['accent']};
        }}
        QPushButton:pressed {{ background-color: {colors['accent_soft']}; }}
        QPushButton:disabled {{ color: {colors['muted']}; background-color: {colors['surface_alt']}; }}
        QPushButton#PrimaryButton {{
            color: #ffffff;
            background-color: {colors['accent']};
            border-color: {colors['accent']};
        }}
        QPushButton#PrimaryButton:hover {{ background-color: {colors['accent_hover']}; }}
        QPushButton#DangerButton {{ color: {colors['danger']}; }}
        QPushButton#NavButton {{
            text-align: left;
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: 10px;
            padding: 11px 12px;
            min-height: 22px;
        }}
        QPushButton#NavButton:checked {{
            color: {colors['accent']};
            background-color: {colors['accent_soft']};
            border-color: {colors['selection']};
        }}
        QPushButton#NavButton:hover:!checked {{ background-color: {colors['surface_hover']}; }}
        QPushButton#SearchScopeButton {{
            color: {colors['muted']};
            background-color: {colors['surface_alt']};
            border: 1px solid {colors['border']};
            border-radius: 16px;
            padding: 7px 14px;
        }}
        QPushButton#SearchScopeButton:checked {{
            color: #ffffff;
            background-color: {colors['accent']};
            border-color: {colors['accent']};
        }}
        QPushButton#SearchScopeButton:hover:!checked {{
            color: {colors['text']};
            background-color: {colors['surface_hover']};
        }}
        QPushButton#ShortcutCard, QPushButton#SuggestionButton {{
            text-align: left;
            background-color: {colors['surface']};
            border: 1px solid {colors['border']};
            border-radius: 11px;
            padding: 12px;
        }}
        QPushButton#ShortcutCard {{ min-height: 68px; }}
        QPushButton#ShortcutCard:hover, QPushButton#SuggestionButton:hover {{
            border-color: {colors['accent']};
            background-color: {colors['surface_hover']};
        }}
        QWidget#SuggestionsCard {{
            background-color: {colors['surface']};
            border: 1px solid {colors['border']};
            border-radius: 13px;
        }}
        QListWidget {{
            color: {colors['text']};
            background-color: {colors['surface_alt']};
            border: 1px solid {colors['border']};
            border-radius: 11px;
            outline: 0;
            padding: 6px;
        }}
        QListWidget::item {{
            padding: 13px 12px;
            margin: 3px;
            border-radius: 8px;
        }}
        QListWidget::item:hover {{ background-color: {colors['surface_hover']}; }}
        QListWidget::item:selected {{
            color: {colors['text']};
            background-color: {colors['selection']};
            border: 1px solid {colors['accent']};
        }}
        QCheckBox::indicator {{
            width: 17px;
            height: 17px;
            border: 1px solid {colors['border']};
            border-radius: 4px;
            background-color: {colors['input']};
        }}
        QCheckBox::indicator:checked {{ background-color: {colors['accent']}; border-color: {colors['accent']}; }}
        QComboBox#ThemeSelector {{ min-width: 88px; }}
        QComboBox QAbstractItemView {{
            color: {colors['text']};
            background-color: {colors['surface']};
            selection-background-color: {colors['selection']};
            border: 1px solid {colors['border']};
        }}
        QStatusBar {{ color: {colors['muted']}; background-color: {colors['window']}; border: none; }}
        QScrollBar:vertical {{ background: {colors['surface']}; width: 10px; margin: 2px; }}
        QScrollBar::handle:vertical {{ background: {colors['border']}; min-height: 26px; border-radius: 5px; }}
        QScrollBar::handle:vertical:hover {{ background: {colors['muted']}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QToolTip {{ color: {colors['text']}; background-color: {colors['surface']}; border: 1px solid {colors['border']}; }}
    """
