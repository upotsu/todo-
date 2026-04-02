
import sqlite3
import sys
from datetime import date, datetime, timedelta

from PySide6.QtCore import QDate, QRect, Qt, Signal, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QTextCharFormat
from PySide6.QtWidgets import (
    QApplication,
    QCalendarWidget,
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QTableView,
)


DB_NAME = "todo_diary_app.db"


def qdate_to_str(qdate: QDate) -> str:
    return qdate.toString("yyyy-MM-dd")


def week_start_for(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return (d - timedelta(days=d.weekday())).isoformat()


def month_key_for(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return f"{d.year:04d}-{d.month:02d}"


class DatabaseManager:
    def __init__(self, db_path: str = DB_NAME):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                title TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                completed_period TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_memos (
                date TEXT PRIMARY KEY,
                content TEXT NOT NULL DEFAULT ''
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS weekly_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start TEXT NOT NULL,
                title TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS monthly_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_month TEXT NOT NULL,
                title TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self.conn.commit()

    def carry_over_open_todos_to_today(self):
        today = date.today().isoformat()
        cur = self.conn.cursor()
        cur.execute(
            """
            UPDATE todos
            SET date = ?
            WHERE completed = 0 AND date < ?
            """,
            (today, today),
        )
        self.conn.commit()

    def add_todo(self, date_str: str, title: str):
        title = title.strip()
        if not title:
            return
        cur = self.conn.cursor()
        cur.execute("INSERT INTO todos (date, title, completed) VALUES (?, ?, 0)", (date_str, title))
        self.conn.commit()

    def fetch_todos(self, date_str: str):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM todos WHERE date = ? ORDER BY completed ASC, id ASC", (date_str,))
        return cur.fetchall()

    def fetch_completed_by_period(self, date_str: str, period: str):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT * FROM todos
            WHERE date = ? AND completed = 1 AND completed_period = ?
            ORDER BY completed_at ASC, id ASC
            """,
            (date_str, period),
        )
        return cur.fetchall()

    def set_todo_completed(self, todo_id: int, completed: bool):
        cur = self.conn.cursor()
        if completed:
            now = datetime.now()
            period = "午前" if now.hour < 12 else "午後"
            cur.execute(
                """
                UPDATE todos
                SET completed = 1, completed_at = ?, completed_period = ?
                WHERE id = ?
                """,
                (now.isoformat(timespec="seconds"), period, todo_id),
            )
        else:
            cur.execute(
                """
                UPDATE todos
                SET completed = 0, completed_at = NULL, completed_period = NULL
                WHERE id = ?
                """,
                (todo_id,),
            )
        self.conn.commit()

    def delete_todo(self, todo_id: int):
        self.conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        self.conn.commit()

    def get_daily_memo(self, date_str: str) -> str:
        cur = self.conn.cursor()
        cur.execute("SELECT content FROM daily_memos WHERE date = ?", (date_str,))
        row = cur.fetchone()
        return row["content"] if row else ""

    def set_daily_memo(self, date_str: str, content: str):
        self.conn.execute(
            """
            INSERT INTO daily_memos (date, content)
            VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET content = excluded.content
            """,
            (date_str, content),
        )
        self.conn.commit()

    def add_weekly_task(self, week_start: str, title: str):
        title = title.strip()
        if not title:
            return
        self.conn.execute(
            "INSERT INTO weekly_tasks (week_start, title, completed) VALUES (?, ?, 0)",
            (week_start, title),
        )
        self.conn.commit()

    def fetch_weekly_tasks(self, week_start: str):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM weekly_tasks WHERE week_start = ? ORDER BY completed ASC, id ASC",
            (week_start,),
        )
        return cur.fetchall()

    def set_weekly_task_completed(self, task_id: int, completed: bool):
        self.conn.execute("UPDATE weekly_tasks SET completed = ? WHERE id = ?", (1 if completed else 0, task_id))
        self.conn.commit()

    def delete_weekly_task(self, task_id: int):
        self.conn.execute("DELETE FROM weekly_tasks WHERE id = ?", (task_id,))
        self.conn.commit()

    def add_monthly_task(self, month_key: str, title: str):
        title = title.strip()
        if not title:
            return
        self.conn.execute(
            "INSERT INTO monthly_tasks (target_month, title, completed) VALUES (?, ?, 0)",
            (month_key, title),
        )
        self.conn.commit()

    def fetch_monthly_tasks(self, month_key: str):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM monthly_tasks WHERE target_month = ? ORDER BY completed ASC, id ASC",
            (month_key,),
        )
        return cur.fetchall()

    def set_monthly_task_completed(self, task_id: int, completed: bool):
        self.conn.execute("UPDATE monthly_tasks SET completed = ? WHERE id = ?", (1 if completed else 0, task_id))
        self.conn.commit()

    def delete_monthly_task(self, task_id: int):
        self.conn.execute("DELETE FROM monthly_tasks WHERE id = ?", (task_id,))
        self.conn.commit()

    def checklist_counts(self, table_name: str, key_name: str, key_value: str):
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS done
            FROM {table_name}
            WHERE {key_name} = ?
            """,
            (key_value,),
        )
        row = cur.fetchone()
        return row["done"] or 0, row["total"] or 0

    def todo_counts_for_range(self, start_date: str, end_date: str):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS done
            FROM todos
            WHERE date >= ? AND date <= ?
            """,
            (start_date, end_date),
        )
        row = cur.fetchone()
        return row["done"] or 0, row["total"] or 0

    def calendar_preview_data(self, year: int, month: int):
        month_prefix = f"{year:04d}-{month:02d}"
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT date, title, completed
            FROM todos
            WHERE substr(date, 1, 7) = ?
            ORDER BY date ASC, completed ASC, id ASC
            """,
            (month_prefix,),
        )
        preview_map: dict[str, list[str]] = {}
        for row in cur.fetchall():
            prefix = "✓ " if row["completed"] else "□ "
            preview_map.setdefault(row["date"], []).append(prefix + row["title"])

        cur.execute(
            """
            SELECT date, content
            FROM daily_memos
            WHERE substr(date, 1, 7) = ? AND trim(content) <> ''
            ORDER BY date ASC
            """,
            (month_prefix,),
        )
        for row in cur.fetchall():
            memo_first = row["content"].strip().splitlines()[0].strip()
            if memo_first:
                preview_map.setdefault(row["date"], []).append("メモ: " + memo_first)

        month_tasks = self.fetch_monthly_tasks(month_prefix)
        first_open = next((r["title"] for r in month_tasks if not r["completed"]), None)
        if first_open:
            note = "★ " + first_open
            for day in range(1, 32):
                try:
                    d = date(year, month, day).isoformat()
                except ValueError:
                    break
                preview_map.setdefault(d, []).append(note)
        return preview_map


class PreviewCalendar(QCalendarWidget):
    dateDoubleClicked = Signal(QDate)

    def __init__(self):
        super().__init__()
        self.preview_map: dict[str, list[str]] = {}
        QTimer.singleShot(0, self._tune_internal_view)

    def _tune_internal_view(self):
        view = self.findChild(QTableView)
        if view:
            try:
                hh = view.horizontalHeader()
                vh = view.verticalHeader()
                vh.setVisible(False)
                hh.setVisible(False)
                hh.setSectionResizeMode(QHeaderView.Stretch)
                view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                view.setContentsMargins(0, 0, 0, 0)
                view.viewport().setContentsMargins(0, 0, 0, 0)
                view.setShowGrid(True)
            except Exception:
                pass

    def showEvent(self, event):
        super().showEvent(event)
        self._tune_internal_view()

    def set_preview_map(self, preview_map: dict[str, list[str]]):
        self.preview_map = preview_map
        self.updateCells()

    def mouseDoubleClickEvent(self, event):
        clicked = self.selectedDate()
        self.dateDoubleClicked.emit(clicked)
        super().mouseDoubleClickEvent(event)

    def paintCell(self, painter: QPainter, rect: QRect, date_obj: QDate):
        painter.save()

        is_current_month = date_obj.month() == self.monthShown()
        is_selected = date_obj == self.selectedDate()
        is_today = date_obj == QDate.currentDate()
        bg = QColor("#fbf8f3")
        if not is_current_month:
            bg = QColor("#f1ece5")
        if is_selected:
            bg = QColor("#d9e8f7")
        elif is_today:
            bg = QColor("#e9f2fc")

        painter.fillRect(rect.adjusted(0, 0, -1, -1), bg)
        painter.setPen(QPen(QColor("#d9c9b8")))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))

        day_color = QColor("#2c2117")
        if date_obj.dayOfWeek() == 7:
            day_color = QColor("#d93333")
        elif date_obj.dayOfWeek() == 6:
            day_color = QColor("#2a5db0")
        if not is_current_month:
            day_color = QColor("#9b948c")

        num_font = QFont(painter.font())
        num_font.setPointSize(11)
        num_font.setBold(True)
        painter.setFont(num_font)
        painter.setPen(day_color)
        num_rect = QRect(rect.left() + 5, rect.top() + 4, rect.width() - 8, 16)
        painter.drawText(num_rect, Qt.AlignLeft | Qt.AlignTop, str(date_obj.day()))

        key = date_obj.toString("yyyy-MM-dd")
        lines = self.preview_map.get(key, [])

        if lines:
            preview_font = QFont(painter.font())
            preview_font.setPointSize(8)
            preview_font.setBold(False)
            painter.setFont(preview_font)
            preview_color = QColor("#4a3929") if is_current_month else QColor("#8a837a")
            painter.setPen(preview_color)

            y = rect.top() + 24
            max_width = rect.width() - 8
            for idx, line in enumerate(lines[:3]):
                shown = line if len(line) <= 12 else line[:11] + "…"
                text_rect = QRect(rect.left() + 4, y + idx * 14, max_width, 14)
                painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, shown)

        painter.restore()


class ChecklistEntryRow(QWidget):
    submitted = Signal(str)
    toggled = Signal(int, bool)
    deleteRequested = Signal(int)

    def __init__(self, item_id=None, text="", checked=False, placeholder="Enterで保存して次を追加"):
        super().__init__()
        self.item_id = item_id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(checked)
        layout.addWidget(self.checkbox)

        self.edit = QLineEdit(text)
        self.edit.setPlaceholderText(placeholder)
        layout.addWidget(self.edit, 1)

        self.delete_btn = QPushButton("削除")
        self.delete_btn.setFixedWidth(52)
        layout.addWidget(self.delete_btn)

        if self.item_id is None:
            self.delete_btn.hide()
        else:
            self.edit.setReadOnly(True)
            if checked:
                self.edit.setStyleSheet("color: #777; text-decoration: line-through;")

        self.edit.returnPressed.connect(self._submit_if_new)
        self.checkbox.toggled.connect(self._toggle)
        self.delete_btn.clicked.connect(self._delete_self)

    def _submit_if_new(self):
        if self.item_id is None:
            text = self.edit.text().strip()
            if text:
                self.submitted.emit(text)

    def _toggle(self, state: bool):
        if self.item_id is not None:
            self.toggled.emit(self.item_id, state)

    def _delete_self(self):
        if self.item_id is not None:
            self.deleteRequested.emit(self.item_id)


class DayEntryDialog(QDialog):
    dataChanged = Signal()

    def __init__(self, db: DatabaseManager, qdate: QDate, parent=None):
        super().__init__(parent)
        self.db = db
        self.qdate = qdate
        self.date_str = qdate_to_str(qdate)
        self.setWindowTitle(f"{self.qdate.toString('yyyy年MM月dd日 (ddd)')} の入力")
        self.resize(700, 760)
        self.build_ui()
        self.refresh()

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel(f"{self.qdate.toString('yyyy年MM月dd日 (ddd)')}")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        info = QLabel("やることに入力して Enter すると保存され、次の空欄が追加されます。")
        info.setStyleSheet("color: #666;")
        layout.addWidget(info)

        task_wrap = QFrame()
        task_layout = QVBoxLayout(task_wrap)
        task_layout.setContentsMargins(10, 10, 10, 10)
        task_layout.setSpacing(6)
        task_layout.addWidget(QLabel("やること"))

        self.tasks_container = QWidget()
        self.tasks_layout = QVBoxLayout(self.tasks_container)
        self.tasks_layout.setContentsMargins(0, 0, 0, 0)
        self.tasks_layout.setSpacing(4)

        tasks_scroll = QScrollArea()
        tasks_scroll.setWidgetResizable(True)
        tasks_scroll.setWidget(self.tasks_container)
        tasks_scroll.setMinimumHeight(260)
        task_layout.addWidget(tasks_scroll)
        layout.addWidget(task_wrap, 1)

        completed_row = QHBoxLayout()
        self.am_list = QListWidget()
        self.pm_list = QListWidget()
        completed_row.addWidget(self.wrap_list("午前に達成", self.am_list))
        completed_row.addWidget(self.wrap_list("午後に達成", self.pm_list))
        layout.addLayout(completed_row)

        memo_box = QFrame()
        memo_layout = QVBoxLayout(memo_box)
        memo_layout.setContentsMargins(10, 10, 10, 10)
        memo_layout.setSpacing(6)
        memo_layout.addWidget(QLabel("メモ / 振り返り"))
        self.memo_edit = QTextEdit()
        self.memo_edit.setPlaceholderText("その日の感想、振り返り、気づきなど")
        self.memo_edit.setMinimumHeight(140)
        memo_layout.addWidget(self.memo_edit)
        save_row = QHBoxLayout()
        save_row.addStretch(1)
        save_btn = QPushButton("メモを保存")
        save_btn.clicked.connect(self.save_memo)
        save_row.addWidget(save_btn)
        memo_layout.addLayout(save_row)
        layout.addWidget(memo_box)

        close_btn = QPushButton("閉じる")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignRight)

    def wrap_list(self, title: str, widget: QListWidget):
        box = QFrame()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(QLabel(title))
        widget.setMinimumHeight(140)
        lay.addWidget(widget)
        return box

    def clear_layout_widgets(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def add_task_row(self, todo_id=None, text="", checked=False, focus=False):
        row = ChecklistEntryRow(todo_id, text, checked, "やることを入力して Enter")
        row.submitted.connect(self.on_submit_new_task)
        row.toggled.connect(self.on_toggle_task)
        row.deleteRequested.connect(self.on_delete_task)
        self.tasks_layout.addWidget(row)
        if focus:
            row.edit.setFocus()
        return row

    def refresh(self):
        self.clear_layout_widgets(self.tasks_layout)
        todos = self.db.fetch_todos(self.date_str)
        for todo in todos:
            self.add_task_row(todo["id"], todo["title"], bool(todo["completed"]))
        self.add_task_row(focus=True)
        self.tasks_layout.addStretch(1)

        self.am_list.clear()
        for row in self.db.fetch_completed_by_period(self.date_str, "午前"):
            self.am_list.addItem(row["title"])

        self.pm_list.clear()
        for row in self.db.fetch_completed_by_period(self.date_str, "午後"):
            self.pm_list.addItem(row["title"])

        self.memo_edit.blockSignals(True)
        self.memo_edit.setPlainText(self.db.get_daily_memo(self.date_str))
        self.memo_edit.blockSignals(False)

    def save_memo(self):
        self.db.set_daily_memo(self.date_str, self.memo_edit.toPlainText())
        self.dataChanged.emit()
        QMessageBox.information(self, "保存", "メモを保存しました。")

    def on_submit_new_task(self, text: str):
        self.db.add_todo(self.date_str, text)
        self.refresh()
        self.dataChanged.emit()

    def on_toggle_task(self, todo_id: int, checked: bool):
        self.db.set_todo_completed(todo_id, checked)
        self.refresh()
        self.dataChanged.emit()

    def on_delete_task(self, todo_id: int):
        self.db.delete_todo(todo_id)
        self.refresh()
        self.dataChanged.emit()


class ChecklistPanel(QFrame):
    changed = Signal()

    def __init__(self, title: str, placeholder: str, fetch_fn, add_fn, toggle_fn, delete_fn, min_height=250):
        super().__init__()
        self.title_text = title
        self.placeholder = placeholder
        self.fetch_fn = fetch_fn
        self.add_fn = add_fn
        self.toggle_fn = toggle_fn
        self.delete_fn = delete_fn

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.title_label)

        self.container = QWidget()
        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.container)
        scroll.setMinimumHeight(min_height)
        layout.addWidget(scroll, 1)

    def set_title(self, title: str):
        self.title_label.setText(title)

    def clear_items(self):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def add_row(self, item_id=None, text="", checked=False, focus=False):
        row = ChecklistEntryRow(item_id, text, checked, self.placeholder)
        row.submitted.connect(self.on_submitted)
        row.toggled.connect(self.on_toggled)
        row.deleteRequested.connect(self.on_deleted)
        self.list_layout.addWidget(row)
        if focus:
            row.edit.setFocus()
        return row

    def refresh(self):
        self.clear_items()
        rows = self.fetch_fn()
        for row in rows:
            self.add_row(row["id"], row["title"], bool(row["completed"]))
        self.add_row(focus=False)
        self.list_layout.addStretch(1)

    def on_submitted(self, text: str):
        self.add_fn(text)
        self.refresh()
        self.changed.emit()

    def on_toggled(self, item_id: int, checked: bool):
        self.toggle_fn(item_id, checked)
        self.refresh()
        self.changed.emit()

    def on_deleted(self, item_id: int):
        self.delete_fn(item_id)
        self.refresh()
        self.changed.emit()


class TodoDiaryApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.db.carry_over_open_todos_to_today()
        self.selected_qdate = QDate.currentDate()
        self.setWindowTitle("Todo・日記カレンダー")
        self.resize(1600, 980)
        self.build_ui()
        self.hook_calendar_nav_buttons()
        self.refresh_all()

    def metric_frame(self, label_text: str):
        frame = QFrame()
        frame.setObjectName("metricFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        title = QLabel(label_text)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 12px; color: #6a4a22;")
        value = QLabel("0%")
        value.setAlignment(Qt.AlignCenter)
        value.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        layout.addWidget(value)
        return frame, value

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(1)

        main_row = QHBoxLayout()
        main_row.setSpacing(6)
        root.addLayout(main_row, 1)

        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.calendar = PreviewCalendar()
        self.calendar.setNavigationBarVisible(True)
        self.calendar.setGridVisible(True)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.calendar.setHorizontalHeaderFormat(QCalendarWidget.NoHorizontalHeader)
        self.calendar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.calendar.setMinimumWidth(1120)
        self.calendar.setMinimumHeight(960)
        self.calendar.clicked.connect(self.on_date_clicked)
        self.calendar.dateDoubleClicked.connect(self.open_day_dialog)
        self.calendar.currentPageChanged.connect(self.refresh_calendar_formats)

        weekday_frame = QFrame()
        weekday_layout = QGridLayout(weekday_frame)
        weekday_layout.setContentsMargins(2, 0, 2, 0)
        weekday_layout.setHorizontalSpacing(0)
        weekday_layout.setVerticalSpacing(0)
        weekday_names = ["日", "月", "火", "水", "木", "金", "土"]
        weekday_colors = ["#d93333", "#2c2117", "#2c2117", "#2c2117", "#2c2117", "#2c2117", "#2a5db0"]
        for i, (name, color) in enumerate(zip(weekday_names, weekday_colors)):
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {color}; padding: 0px; margin: 0px;")
            weekday_layout.addWidget(lbl, 0, i)
        left_layout.addWidget(weekday_frame, 0)
        left_layout.addWidget(self.calendar, 1)

        right_panel = self.build_right_panel()
        main_row.addWidget(left_panel, 7)
        main_row.addWidget(right_panel, 2)

        self.apply_styles()

    def build_right_panel(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        scroll.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 0, 4, 4)
        layout.setSpacing(8)

        metric_row = QHBoxLayout()
        metric_row.setSpacing(8)
        metric1, self.today_rate_value = self.metric_frame("今日")
        metric2, self.week_rate_value = self.metric_frame("今週")
        metric3, self.month_rate_value = self.metric_frame("今月")
        metric_row.addWidget(metric1)
        metric_row.addWidget(metric2)
        metric_row.addWidget(metric3)
        layout.addLayout(metric_row)

        self.week_panel = ChecklistPanel(
            "今週の目標",
            "今週の目標を入力して Enter",
            self.fetch_weekly_panel_data,
            self.add_weekly_panel_item,
            self.toggle_weekly_panel_item,
            self.delete_weekly_panel_item,
            320,
        )
        self.week_panel.changed.connect(self.refresh_all)
        layout.addWidget(self.week_panel)

        self.month_panel = ChecklistPanel(
            "今月の目標",
            "今月の目標を入力して Enter",
            self.fetch_monthly_panel_data,
            self.add_monthly_panel_item,
            self.toggle_monthly_panel_item,
            self.delete_monthly_panel_item,
            320,
        )
        self.month_panel.changed.connect(self.refresh_all)
        layout.addWidget(self.month_panel)

        summary_box = QFrame()
        summary_layout = QVBoxLayout(summary_box)
        summary_layout.setContentsMargins(10, 10, 10, 10)
        summary_layout.setSpacing(6)
        s_title = QLabel("進捗サマリー")
        s_title.setStyleSheet("font-size: 15px; font-weight: bold;")
        summary_layout.addWidget(s_title)
        self.summary_today = QLabel()
        self.summary_week = QLabel()
        self.summary_month = QLabel()
        self.summary_week_goal = QLabel()
        self.summary_month_goal = QLabel()
        summary_layout.addWidget(self.summary_today)
        summary_layout.addWidget(self.summary_week)
        summary_layout.addWidget(self.summary_month)
        summary_layout.addWidget(self.summary_week_goal)
        summary_layout.addWidget(self.summary_month_goal)
        layout.addWidget(summary_box)

        layout.addStretch(1)
        return scroll

    def hook_calendar_nav_buttons(self):
        for button in self.calendar.findChildren(QToolButton):
            text = button.text().strip()
            if text in ("<", "◀", "◁"):
                try:
                    button.clicked.disconnect()
                except Exception:
                    pass
                button.clicked.connect(self.calendar.showPreviousMonth)
            elif text in (">", "▶", "▷"):
                try:
                    button.clicked.disconnect()
                except Exception:
                    pass
                button.clicked.connect(self.calendar.showNextMonth)

    def apply_styles(self):
        self.setStyleSheet(
            """
            QWidget {
                background: #f5f1ea;
                color: #2c2117;
                font-size: 13px;
            }
            QFrame, QScrollArea, QListWidget, QTextEdit, QLineEdit {
                border: 1px solid #d4b08a;
                border-radius: 8px;
                background: #fbf8f3;
            }
            QPushButton {
                background: #e4a55e;
                border: none;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #d89349;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background: #edd8bb;
                border: 1px solid #d4b08a;
                border-radius: 8px;
                min-height: 32px;
                max-height: 34px;
            }
            QCalendarWidget QToolButton {
                min-width: 28px;
                min-height: 24px;
                border-radius: 6px;
                background: transparent;
                font-weight: bold;
            }
            QCalendarWidget QToolButton:hover {
                background: #e7c99f;
            }
            QCalendarWidget QAbstractItemView:enabled {
                selection-background-color: transparent;
                selection-color: transparent;
                gridline-color: #d9c9b8;
                outline: 0;
                font-size: 12px;
            }
            QCalendarWidget QTableView {
                alternate-background-color: #fbf8f3;
            }
            QHeaderView::section {
                background: #f0e4d4;
                color: #6a4a22;
                border: 1px solid #d9c9b8;
                height: 24px;
                max-height: 24px;
                min-height: 24px;
                font-size: 11px;
                font-weight: bold;
            }
            QFrame#metricFrame {
                min-width: 118px;
            }
            """
        )

    def selected_date_str(self) -> str:
        return qdate_to_str(self.selected_qdate)

    def current_week_start(self) -> str:
        return week_start_for(self.selected_date_str())

    def current_month_key(self) -> str:
        return month_key_for(self.selected_date_str())

    def fetch_weekly_panel_data(self):
        return self.db.fetch_weekly_tasks(self.current_week_start())

    def add_weekly_panel_item(self, text: str):
        self.db.add_weekly_task(self.current_week_start(), text)

    def toggle_weekly_panel_item(self, item_id: int, checked: bool):
        self.db.set_weekly_task_completed(item_id, checked)

    def delete_weekly_panel_item(self, item_id: int):
        self.db.delete_weekly_task(item_id)

    def fetch_monthly_panel_data(self):
        return self.db.fetch_monthly_tasks(self.current_month_key())

    def add_monthly_panel_item(self, text: str):
        self.db.add_monthly_task(self.current_month_key(), text)

    def toggle_monthly_panel_item(self, item_id: int, checked: bool):
        self.db.set_monthly_task_completed(item_id, checked)

    def delete_monthly_panel_item(self, item_id: int):
        self.db.delete_monthly_task(item_id)

    def open_day_dialog(self, qdate: QDate | None = None):
        if qdate is None:
            qdate = self.selected_qdate
        else:
            self.selected_qdate = qdate
        dialog = DayEntryDialog(self.db, qdate, self)
        dialog.dataChanged.connect(self.refresh_all)
        dialog.exec()
        self.refresh_all()

    def on_date_clicked(self, qdate: QDate):
        self.selected_qdate = qdate
        self.open_day_dialog(qdate)

    def rate_text(self, done: int, total: int) -> str:
        rate = int(round(done * 100 / total)) if total else 0
        return f"{rate}% ({done}/{total})"

    def set_metric(self, label: QLabel, done: int, total: int):
        label.setText(f"{int(round(done * 100 / total)) if total else 0}%")

    def refresh_panels(self):
        self.week_panel.set_title(f"今週の目標（週開始: {self.current_week_start()}）")
        self.month_panel.set_title(f"今月の目標（{self.current_month_key()}）")
        self.week_panel.refresh()
        self.month_panel.refresh()

    def refresh_metrics(self):
        selected = self.selected_date_str()
        today_done, today_total = self.db.todo_counts_for_range(selected, selected)
        self.set_metric(self.today_rate_value, today_done, today_total)

        week_start = self.current_week_start()
        week_end = (datetime.strptime(week_start, "%Y-%m-%d").date() + timedelta(days=6)).isoformat()
        week_done, week_total = self.db.todo_counts_for_range(week_start, week_end)
        self.set_metric(self.week_rate_value, week_done, week_total)

        month_key = self.current_month_key()
        first = month_key + "-01"
        year, month = map(int, month_key.split("-"))
        if month == 12:
            month_end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end_date = date(year, month + 1, 1) - timedelta(days=1)
        month_done, month_total = self.db.todo_counts_for_range(first, month_end_date.isoformat())
        self.set_metric(self.month_rate_value, month_done, month_total)

        week_goal_done, week_goal_total = self.db.checklist_counts("weekly_tasks", "week_start", week_start)
        month_goal_done, month_goal_total = self.db.checklist_counts("monthly_tasks", "target_month", month_key)

        self.summary_today.setText(f"今日の達成率: {self.rate_text(today_done, today_total)}")
        self.summary_week.setText(f"今週の達成率: {self.rate_text(week_done, week_total)}")
        self.summary_month.setText(f"今月の達成率: {self.rate_text(month_done, month_total)}")
        self.summary_week_goal.setText(f"今週の目標達成率: {self.rate_text(week_goal_done, week_goal_total)}")
        self.summary_month_goal.setText(f"今月の目標達成率: {self.rate_text(month_goal_done, month_goal_total)}")

    def refresh_calendar_formats(self):
        year = self.calendar.yearShown()
        month = self.calendar.monthShown()
        preview = self.db.calendar_preview_data(year, month)
        self.calendar.set_preview_map(preview)

        transparent_fmt = QTextCharFormat()
        transparent_fmt.setForeground(QColor(0, 0, 0, 0))
        for m in (month - 1, month, month + 1):
            yy, mm = year, m
            if mm < 1:
                yy -= 1
                mm = 12
            elif mm > 12:
                yy += 1
                mm = 1
            for day in range(1, 32):
                qd = QDate(yy, mm, day)
                if qd.isValid():
                    self.calendar.setDateTextFormat(qd, transparent_fmt)

    def refresh_all(self):
        self.db.carry_over_open_todos_to_today()
        self.refresh_panels()
        self.refresh_metrics()
        self.refresh_calendar_formats()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TodoDiaryApp()
    window.show()
    sys.exit(app.exec())
