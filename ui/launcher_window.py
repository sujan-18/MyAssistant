"""Keyboard-first launcher UI connected to application search services."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from core.application import LauncherItem, LauncherSearchResults
from ui.theme import application_stylesheet


class SearchInput(QLineEdit):
    move_selection = Signal(int)
    activate_selection = Signal()
    dismiss = Signal()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override name
        if event.key() == Qt.Key.Key_Down:
            self.move_selection.emit(1)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Up:
            self.move_selection.emit(-1)
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.activate_selection.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.dismiss.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class LauncherWindow(QMainWindow):
    """Render catalog search results and open only the explicitly selected app."""

    result_activated = Signal(object)
    exit_requested = Signal()
    hidden = Signal()

    def __init__(
        self,
        search_applications: Callable[[str], LauncherSearchResults],
        open_application: Callable[[LauncherItem], None],
        task_panel: QWidget | None = None,
        voice_panel: QWidget | None = None,
    ) -> None:
        super().__init__()
        self._search_applications = search_applications
        self._open_application = open_application
        self._tray_available = False
        self.setWindowTitle("MyAssistant")
        self.setMinimumSize(920, 620)
        self.resize(1180, 760)

        shell = QWidget(self)
        shell.setObjectName("AppShell")
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(205)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(17, 20, 17, 18)
        sidebar_layout.setSpacing(9)
        brand_mark = QLabel("M")
        brand_mark.setObjectName("BrandMark")
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(brand_mark, 0, Qt.AlignmentFlag.AlignLeft)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(1)
        brand_title = QLabel("MyAssistant")
        brand_title.setObjectName("BrandTitle")
        brand_subtitle = QLabel("Your desktop, in one place")
        brand_subtitle.setObjectName("BrandSubtitle")
        brand_text.addWidget(brand_title)
        brand_text.addWidget(brand_subtitle)
        sidebar_layout.addLayout(brand_text)
        sidebar_layout.addSpacing(24)

        self.pages = QStackedWidget()
        self.pages.setObjectName("PageStack")
        self._nav_buttons: dict[str, QPushButton] = {}
        for key, label, glyph in (
            ("home", "Home", "⌂"),
            ("tasks", "Tasks", "✓"),
            ("voice", "Voice", "♫"),
        ):
            button = self._make_nav_button(key, label, glyph)
            sidebar_layout.addWidget(button)
            self._nav_buttons[key] = button
        separator = QWidget()
        separator.setObjectName("SidebarSeparator")
        separator.setFixedHeight(1)
        sidebar_layout.addWidget(separator)
        for key, label, glyph in (("settings", "Settings", "⚙"), ("help", "Help", "?")):
            button = self._make_nav_button(key, label, glyph)
            sidebar_layout.addWidget(button)
            self._nav_buttons[key] = button
        sidebar_layout.addStretch(1)
        appearance_label = QLabel("Appearance")
        appearance_label.setObjectName("SidebarLabel")
        sidebar_layout.addWidget(appearance_label)
        self.theme_selector = QComboBox()
        self.theme_selector.setObjectName("ThemeSelector")
        self.theme_selector.setAccessibleName("Color theme")
        self.theme_selector.addItem("Light", "light")
        self.theme_selector.addItem("Dark", "dark")
        self._theme_settings = QSettings("MyAssistant", "MyAssistant")
        saved_theme = self._theme_settings.value("appearance/theme", "light", type=str)
        theme_index = self.theme_selector.findData(saved_theme)
        self.theme_selector.setCurrentIndex(theme_index if theme_index >= 0 else 0)
        self.theme_selector.currentIndexChanged.connect(self._theme_changed)
        sidebar_layout.addWidget(self.theme_selector)
        shell_layout.addWidget(sidebar)

        self.home_page = QWidget()
        self.home_page.setObjectName("HomePage")
        home_layout = QHBoxLayout(self.home_page)
        home_layout.setContentsMargins(27, 24, 23, 24)
        home_layout.setSpacing(20)

        main_column = QVBoxLayout()
        main_column.setSpacing(14)
        greeting = QLabel("✦  Hello!")
        greeting.setObjectName("Greeting")
        main_column.addWidget(greeting)
        description = QLabel("What are you looking for today? 👋")
        description.setObjectName("WelcomeLine")
        main_column.addWidget(description)
        self.search_input = SearchInput()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText("Search applications, files, and folders…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._refresh_results)
        self.search_input.move_selection.connect(self._move_selection)
        self.search_input.activate_selection.connect(self._activate_current)
        self.search_input.dismiss.connect(self.hide)
        main_column.addWidget(self.search_input)

        self.match_notice = QLabel("Search your discovered applications and indexed locations")
        self.match_notice.setObjectName("MatchNotice")
        self.match_notice.setWordWrap(True)
        main_column.addWidget(self.match_notice)

        self.results = QListWidget()
        self.results.setObjectName("Results")
        self.results.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.results.itemDoubleClicked.connect(self._activate_item)
        self.results.setMaximumHeight(190)
        self.results.hide()
        main_column.addWidget(self.results)

        shortcuts = QGridLayout()
        shortcuts.setHorizontalSpacing(10)
        shortcuts.setVerticalSpacing(10)
        self._add_shortcut(shortcuts, 0, 0, "Find Files", "Search your files and folders", "▱", lambda: self._focus_search(""))
        self._add_shortcut(shortcuts, 0, 1, "Open App", "Launch your applications", "▦", lambda: self._focus_search(""))
        self._add_shortcut(shortcuts, 1, 0, "Quick Tasks", "Get things done faster", "✓", lambda: self._show_page("tasks"))
        self._add_shortcut(shortcuts, 1, 1, "Voice Search", "Speak and search", "♫", lambda: self._show_page("voice"))
        main_column.addLayout(shortcuts)
        main_column.addStretch(1)
        home_layout.addLayout(main_column, 3)

        suggestions = QWidget()
        suggestions.setObjectName("SuggestionsCard")
        suggestions_layout = QVBoxLayout(suggestions)
        suggestions_layout.setContentsMargins(15, 15, 15, 15)
        suggestions_layout.setSpacing(9)
        suggestions_heading = QLabel("Quick Suggestions")
        suggestions_heading.setObjectName("CardHeading")
        suggestions_layout.addWidget(suggestions_heading)
        for title, query in (
            ("Search applications", ""),
            ("Find documents", "documents"),
        ):
            action = QPushButton(f"⌕   {title}")
            action.setObjectName("SuggestionButton")
            action.clicked.connect(lambda _checked=False, value=query: self._focus_search(value))
            suggestions_layout.addWidget(action)
        tasks_action = QPushButton("✓   Open tasks")
        tasks_action.setObjectName("SuggestionButton")
        tasks_action.clicked.connect(lambda: self._show_page("tasks"))
        suggestions_layout.addWidget(tasks_action)
        settings_action = QPushButton("⚙   Open settings")
        settings_action.setObjectName("SuggestionButton")
        settings_action.clicked.connect(lambda: self._show_page("settings"))
        suggestions_layout.addWidget(settings_action)
        suggestions_layout.addStretch(1)
        home_layout.addWidget(suggestions, 1)

        self.pages.addWidget(self.home_page)
        self._page_indices = {"home": 0}
        if task_panel is not None:
            self.pages.addWidget(task_panel)
            self._page_indices["tasks"] = self.pages.count() - 1
        if voice_panel is not None:
            self.pages.addWidget(voice_panel)
            self._page_indices["voice"] = self.pages.count() - 1
        self.pages.addWidget(self._make_settings_page())
        self._page_indices["settings"] = self.pages.count() - 1
        self.pages.addWidget(self._make_help_page())
        self._page_indices["help"] = self.pages.count() - 1
        shell_layout.addWidget(self.pages, 1)
        self.setCentralWidget(shell)
        self._show_page("home")
        self._apply_theme(self.theme_selector.currentData())
        self.statusBar().showMessage("Welcome to MyAssistant. Search apps, files, and folders.")

        self.exit_action = QAction("Exit MyAssistant", self)
        self.exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        self.exit_action.triggered.connect(self.exit_requested.emit)
        self.addAction(self.exit_action)

        self._refresh_results("")

    def _make_nav_button(self, key: str, label: str, glyph: str) -> QPushButton:
        button = QPushButton(f"{glyph}    {label}")
        button.setObjectName("NavButton")
        button.setCheckable(True)
        button.clicked.connect(lambda _checked=False, page=key: self._show_page(page))
        return button

    def _show_page(self, page: str) -> None:
        index = self._page_indices.get(page)
        if index is None:
            return
        self.pages.setCurrentIndex(index)
        for key, button in self._nav_buttons.items():
            button.setChecked(key == page)
        if page == "home":
            self.search_input.setFocus(Qt.FocusReason.OtherFocusReason)

    def _focus_search(self, query: str) -> None:
        self._show_page("home")
        self.search_input.setText(query)
        self.search_input.setFocus(Qt.FocusReason.OtherFocusReason)
        self.search_input.selectAll()

    def _add_shortcut(self, layout: QGridLayout, row: int, column: int, title: str,
                      detail: str, glyph: str, callback: Callable[[], None]) -> None:
        button = QPushButton(f"{glyph}   {title}\n{detail}    ›")
        button.setObjectName("ShortcutCard")
        button.setMinimumHeight(76)
        button.setStyleSheet("text-align: left; white-space: pre-wrap;")
        button.clicked.connect(callback)
        layout.addWidget(button, row, column)

    def _make_settings_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("ContentPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 24)
        heading = QLabel("Settings")
        heading.setObjectName("PageHeading")
        layout.addWidget(heading)
        layout.addWidget(QLabel("Choose how MyAssistant looks. Your choice is saved automatically."))
        layout.addWidget(QLabel("Use the appearance selector at the bottom of the navigation bar to switch between Light and Dark."))
        layout.addStretch(1)
        return page

    def _make_help_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("ContentPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 24)
        heading = QLabel("Help")
        heading.setObjectName("PageHeading")
        layout.addWidget(heading)
        layout.addWidget(QLabel("Search applications and configured file locations from Home. Use Tasks to manage deadlines and Voice for local speech features."))
        layout.addStretch(1)
        return page

    def _theme_changed(self, _index: int) -> None:
        theme = self.theme_selector.currentData()
        if theme in {"light", "dark"}:
            self._theme_settings.setValue("appearance/theme", theme)
            self._apply_theme(theme)

    def _apply_theme(self, theme: str) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(application_stylesheet(theme))

    def _refresh_results(self, query: str) -> None:
        try:
            search = self._search_applications(query)
        except Exception as exc:
            self.results.clear()
            self.match_notice.setText("Search is temporarily unavailable.")
            self.statusBar().showMessage(f"Search failed: {exc}")
            return
        self.results.clear()
        for result in search.matches:
            item = QListWidgetItem(f"{result.name}\n{result.kind}  ·  {result.target}")
            item.setData(Qt.ItemDataRole.UserRole, result)
            self.results.addItem(item)
        self.results.setVisible(bool(query.strip()) and self.results.count() > 0)
        if search.ambiguous:
            self.match_notice.setText("Several results match equally. Choose the intended result.")
        else:
            self.match_notice.setText("Search your discovered applications and indexed locations")
        if self.results.count():
            self.results.setCurrentRow(0)
            self.statusBar().showMessage(f"{self.results.count()} result(s). Press Enter to open.")
        else:
            message = "No results found." if query.strip() else "Type to search applications, files, and folders."
            self.statusBar().showMessage(message)

    def _move_selection(self, offset: int) -> None:
        count = self.results.count()
        if count == 0:
            return
        current = self.results.currentRow()
        self.results.setCurrentRow((current + offset) % count)

    def _activate_current(self) -> None:
        item = self.results.currentItem()
        if item is not None:
            self._activate_item(item)

    def _activate_item(self, item: QListWidgetItem) -> None:
        result = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(result, LauncherItem):
            try:
                self._open_application(result)
            except Exception as exc:
                self.statusBar().showMessage(f"Could not open {result.name}: {exc}")
                return
            self.result_activated.emit(result)
            self.statusBar().showMessage(f"Opened {result.name}.")
            self.hide()

    def show_and_focus(self) -> None:
        self.show()
        screen = QApplication.primaryScreen()
        if screen is not None:
            bounds = screen.availableGeometry()
            self.move(bounds.center() - self.rect().center())
        self.raise_()
        self.activateWindow()
        # Window activation is asynchronous on Windows. Focus after Qt has
        # completed the show/activation event so reopening behaves consistently.
        QTimer.singleShot(0, lambda: self.search_input.setFocus(Qt.FocusReason.OtherFocusReason))

    def toggle_visible(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show_and_focus()

    def set_tray_available(self, available: bool) -> None:
        self._tray_available = available

    def set_index_status(self, text: str) -> None:
        self.match_notice.setText(text)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override name
        if self._tray_available:
            event.ignore()
            self.hide()
        else:
            event.accept()
            self.exit_requested.emit()

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt override name
        self.hidden.emit()
        super().hideEvent(event)


def create_application(argv: list[str] | None = None) -> QApplication:
    """Create a Qt application that remains alive while the launcher is hidden."""
    app = QApplication.instance()
    if app is None:
        import sys

        app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName("MyAssistant")
    app.setQuitOnLastWindowClosed(False)
    return app
