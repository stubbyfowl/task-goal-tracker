import json
import sys
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import List, Optional, Tuple


def get_data_file() -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        data_dir = home / "Library" / "Application Support" / "TaskGoalTracker"
    else:
        data_dir = home / ".local" / "share" / "TaskGoalTracker"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "tracker_data.json"


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


@dataclass
class TaskItem:
    text: str
    done: bool = False
    due_date: str = ""
    subtasks: List["TaskItem"] = field(default_factory=list)
    recurring: bool = False
    last_done_date: str = ""


@dataclass
class GoalItem:
    title: str
    notes: str = ""
    due_date: str = ""
    tasks: List[TaskItem] = field(default_factory=list)


# ── Palette ──────────────────────────────────────────────────────────────────
LIGHT = {
    "bg":          "#f0f0ef",   # warm off-white / marble base
    "surface":     "#fafaf9",   # card surface
    "surface2":    "#f4f3f1",   # subtle secondary surface
    "border":      "#dddbd8",   # soft stone border
    "text":        "#1c1c1a",   # near-black
    "muted":       "#8a887f",   # warm stone gray
    "accent":      "#4a4a48",   # dark charcoal for buttons
    "accent_fg":   "#ffffff",
    "daily_fg":    "#5b7fa6",   # muted slate-blue for recurring
    "done_fg":     "#aaa89f",   # faded for completed
    "select_bg":   "#e6e4e0",
    "select_fg":   "#1c1c1a",
    "input_bg":    "#ffffff",
    "input_fg":    "#1c1c1a",
    "hover":       "#e8e6e2",
}

DARK = {
    "bg":          "#161614",
    "surface":     "#1e1e1b",
    "surface2":    "#252522",
    "border":      "#2e2e2a",
    "text":        "#f0ede8",
    "muted":       "#7a786f",
    "accent":      "#d4d0c8",
    "accent_fg":   "#161614",
    "daily_fg":    "#7baad4",
    "done_fg":     "#4a4844",
    "select_bg":   "#2e2e2a",
    "select_fg":   "#f0ede8",
    "input_bg":    "#1a1a17",
    "input_fg":    "#f0ede8",
    "hover":       "#242420",
}


class DuePicker:
    def __init__(self, parent: tk.Widget, palette: dict):
        self.frame = tk.Frame(parent, bg=palette["surface"])
        self.month = tk.StringVar(value="--")
        self.day = tk.StringVar(value="--")
        self.hour = tk.StringVar(value="--")
        self.minute = tk.StringVar(value="--")
        self._palette = palette

        months  = ["--"] + [f"{i:02d}" for i in range(1, 13)]
        days    = ["--"] + [f"{i:02d}" for i in range(1, 32)]
        hours   = ["--"] + [f"{i:02d}" for i in range(0, 24)]
        minutes = ["--"] + [f"{i:02d}" for i in range(0, 60)]

        self._combo(self.month,  months,  4).pack(side="left")
        tk.Label(self.frame, text="/", bg=palette["surface"], fg=palette["muted"],
                 font=("Helvetica", 11)).pack(side="left", padx=3)
        self._combo(self.day,    days,    4).pack(side="left")
        tk.Label(self.frame, text=" ", bg=palette["surface"]).pack(side="left", padx=4)
        self._combo(self.hour,   hours,   4).pack(side="left")
        tk.Label(self.frame, text=":", bg=palette["surface"], fg=palette["muted"],
                 font=("Helvetica", 11)).pack(side="left", padx=3)
        self._combo(self.minute, minutes, 4).pack(side="left")

    def _combo(self, var, values, width):
        cb = ttk.Combobox(self.frame, textvariable=var, values=values,
                          width=width, state="readonly", style="Marble.TCombobox")
        return cb

    def set_value(self, value: str) -> None:
        if not value:
            self.clear(); return
        try:
            p = datetime.strptime(value, "%m-%d %H:%M")
            self.month.set(p.strftime("%m")); self.day.set(p.strftime("%d"))
            self.hour.set(p.strftime("%H")); self.minute.set(p.strftime("%M"))
        except ValueError:
            self.clear()

    def get_value(self) -> str:
        parts = [self.month.get(), self.day.get(), self.hour.get(), self.minute.get()]
        if any(p == "--" for p in parts):
            return ""
        mm, dd, hh, mn = parts
        dt = datetime.strptime(f"{mm}-{dd} {hh}:{mn}", "%m-%d %H:%M")
        return dt.strftime("%m-%d %H:%M")

    def clear(self) -> None:
        self.month.set("--"); self.day.set("--")
        self.hour.set("--"); self.minute.set("--")

    def recolor(self, palette: dict) -> None:
        self._palette = palette
        self.frame.configure(bg=palette["surface"])
        for w in self.frame.winfo_children():
            if isinstance(w, tk.Label):
                w.configure(bg=palette["surface"], fg=palette["muted"])


class DataStore:
    def __init__(self, path: Path):
        self.path = path
        self.data = {"tasks": [], "goals": []}
        self.load()

    def _load_task(self, item: dict) -> TaskItem:
        raw = item.get("subtasks", [])
        subs = [self._load_task(s) for s in raw] if isinstance(raw, list) else []
        return TaskItem(
            text=item.get("text", ""),
            done=bool(item.get("done", False)),
            due_date=item.get("due_date", ""),
            subtasks=subs,
            recurring=bool(item.get("recurring", False)),
            last_done_date=item.get("last_done_date", ""),
        )

    def load(self) -> None:
        if not self.path.exists():
            self.save(); return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            tasks = [self._load_task(i) for i in raw.get("tasks", [])]
            goals = []
            for gr in raw.get("goals", []):
                tasks_raw = gr.get("tasks", gr.get("checklist", []))
                goals.append(GoalItem(
                    title=gr.get("title", ""),
                    notes=gr.get("notes", ""),
                    due_date=gr.get("due_date", ""),
                    tasks=[self._load_task(t) for t in tasks_raw],
                ))
            self.data = {"tasks": tasks, "goals": goals}
        except Exception:
            self.data = {"tasks": [], "goals": []}
            messagebox.showwarning("Data Warning", "Could not read saved data. Starting fresh.")

    def save(self) -> None:
        s = {"tasks": [asdict(t) for t in self.data["tasks"]],
             "goals": [asdict(g) for g in self.data["goals"]]}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(s, indent=2), encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("Save Error", f"Could not save:\n\n{exc}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def marble_button(parent, text, command, p, small=False):
    """Flat, bordered button with marble palette."""
    size = 9 if small else 10
    btn = tk.Button(
        parent, text=text, command=command,
        bg=p["surface2"], fg=p["text"],
        activebackground=p["hover"], activeforeground=p["text"],
        relief="flat", bd=0,
        font=("Helvetica", size),
        padx=14 if not small else 10,
        pady=6 if not small else 4,
        cursor="hand2",
    )
    return btn


def danger_button(parent, text, command, p, small=False):
    size = 9 if small else 10
    btn = tk.Button(
        parent, text=text, command=command,
        bg=p["surface2"], fg="#b05050",
        activebackground="#f0e4e4", activeforeground="#8b2020",
        relief="flat", bd=0,
        font=("Helvetica", size),
        padx=14 if not small else 10,
        pady=6 if not small else 4,
        cursor="hand2",
    )
    return btn


def section_sep(parent, p):
    tk.Frame(parent, height=1, bg=p["border"]).pack(fill="x", pady=8)


class TrackerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Tracker")
        self.root.geometry("1080x700")
        self.root.minsize(780, 520)

        self.store = DataStore(get_data_file())
        self.tasks: List[TaskItem] = self.store.data["tasks"]
        self.goals: List[GoalItem] = self.store.data["goals"]
        self.dark_mode = tk.BooleanVar(value=False)
        self._p = LIGHT  # active palette

        self._reset_recurring_tasks()
        self._configure_style()
        self._build_ui()
        self.refresh_tasks()
        self.refresh_goals()

    # ── Recurring reset ───────────────────────────────────────────────────────
    def _reset_recurring_tasks(self) -> None:
        today = today_str()
        changed = False
        for task in self.tasks:
            if task.recurring and task.done and task.last_done_date != today:
                task.done = False
                changed = True
        if changed:
            self.store.save()

    # ── Style ─────────────────────────────────────────────────────────────────
    def _configure_style(self) -> None:
        self.style = ttk.Style(self.root)
        if "clam" in self.style.theme_names():
            self.style.theme_use("clam")
        self._apply_theme()

    def _apply_theme(self) -> None:
        p = DARK if self.dark_mode.get() else LIGHT
        self._p = p

        self.root.configure(bg=p["bg"])

        self.style.configure("TFrame",        background=p["bg"])
        self.style.configure("Surface.TFrame", background=p["surface"])
        self.style.configure("S2.TFrame",      background=p["surface2"])

        self.style.configure("TLabel",
            background=p["bg"], foreground=p["text"],
            font=("Helvetica", 11))
        self.style.configure("Muted.TLabel",
            background=p["bg"], foreground=p["muted"],
            font=("Helvetica", 10))
        self.style.configure("Head.TLabel",
            background=p["bg"], foreground=p["text"],
            font=("Helvetica", 20, "bold"))
        self.style.configure("Sub.TLabel",
            background=p["bg"], foreground=p["muted"],
            font=("Helvetica", 11))
        self.style.configure("GoalHead.TLabel",
            background=p["surface"], foreground=p["text"],
            font=("Helvetica", 14, "bold"))
        self.style.configure("GoalMuted.TLabel",
            background=p["surface"], foreground=p["muted"],
            font=("Helvetica", 10))

        self.style.configure("TNotebook",
            background=p["bg"], borderwidth=0, tabmargins=0)
        self.style.configure("TNotebook.Tab",
            background=p["bg"], foreground=p["muted"],
            font=("Helvetica", 11), padding=(20, 10))
        self.style.map("TNotebook.Tab",
            background=[("selected", p["surface"]), ("!selected", p["bg"])],
            foreground=[("selected", p["text"]),    ("!selected", p["muted"])])

        self.style.configure("Treeview",
            rowheight=32, font=("Helvetica", 10),
            background=p["surface"], foreground=p["text"],
            fieldbackground=p["surface"], borderwidth=0, relief="flat")
        self.style.configure("Treeview.Heading",
            font=("Helvetica", 9, "bold"),
            background=p["surface2"], foreground=p["muted"],
            relief="flat", borderwidth=0)
        self.style.map("Treeview",
            background=[("selected", p["select_bg"])],
            foreground=[("selected", p["select_fg"])])

        self.style.configure("Marble.TCombobox",
            fieldbackground=p["input_bg"], background=p["surface2"],
            foreground=p["input_fg"], arrowcolor=p["muted"],
            bordercolor=p["border"], relief="flat")

        self.style.configure("TEntry",
            fieldbackground=p["input_bg"], foreground=p["input_fg"],
            insertcolor=p["text"], relief="flat",
            bordercolor=p["border"], padding=8)

        self.style.configure("Marble.TCheckbutton",
            background=p["bg"], foreground=p["muted"],
            font=("Helvetica", 10))

        self._recolor_widgets()

    def _recolor_widgets(self) -> None:
        p = self._p
        # recolor all tracked tk widgets
        for attr in ("_all_tk_labels", "_all_tk_frames", "_all_buttons"):
            if not hasattr(self, attr):
                continue
        # recolor specific named widgets
        for name in ("goals_list", "goal_notes", "sidebar_frame",
                     "right_frame", "task_entry", "goal_entry", "goal_item_entry"):
            if not hasattr(self, name):
                continue
            w = getattr(self, name)
            try:
                if isinstance(w, tk.Listbox):
                    w.configure(bg=p["surface"], fg=p["text"],
                                selectbackground=p["select_bg"],
                                selectforeground=p["select_fg"],
                                highlightthickness=0, relief="flat")
                elif isinstance(w, tk.Text):
                    w.configure(bg=p["input_bg"], fg=p["input_fg"],
                                insertbackground=p["input_fg"],
                                highlightthickness=0, relief="flat")
                elif isinstance(w, tk.Entry):
                    w.configure(bg=p["input_bg"], fg=p["input_fg"],
                                insertbackground=p["input_fg"],
                                relief="flat", highlightthickness=1,
                                highlightbackground=p["border"])
            except Exception:
                pass
        # due pickers
        for dp in getattr(self, "_due_pickers", []):
            dp.recolor(p)
        # treeview tags
        for tv in getattr(self, "_treeviews", []):
            try:
                tv.tag_configure("recurring", foreground=p["daily_fg"])
                tv.tag_configure("done",      foreground=p["done_fg"])
            except Exception:
                pass

    def toggle_dark_mode(self) -> None:
        self._apply_theme()

    # ── UI skeleton ───────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        p = self._p
        self.root.configure(bg=p["bg"])

        # ── Top bar
        topbar = tk.Frame(self.root, bg=p["bg"])
        topbar.pack(fill="x", padx=28, pady=(20, 0))

        tk.Label(topbar, text="Tracker", bg=p["bg"], fg=p["text"],
                 font=("Helvetica", 22, "bold")).pack(side="left")
        tk.Label(topbar, text=datetime.now().strftime("%A, %B %d"),
                 bg=p["bg"], fg=p["muted"],
                 font=("Helvetica", 12)).pack(side="left", padx=(14, 0), pady=(4, 0))

        # Dark mode toggle (right side)
        dark_cb = ttk.Checkbutton(topbar, text="Dark mode",
                                   variable=self.dark_mode,
                                   command=lambda: self.safe(self.toggle_dark_mode),
                                   style="Marble.TCheckbutton")
        dark_cb.pack(side="right")

        # ── Thin rule
        tk.Frame(self.root, height=1, bg=p["border"]).pack(fill="x", padx=28, pady=(12, 0))

        # ── Notebook
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=0, pady=0)

        self.tasks_tab = tk.Frame(self.nb, bg=p["bg"])
        self.goals_tab = tk.Frame(self.nb, bg=p["bg"])
        self.nb.add(self.tasks_tab, text="  Tasks  ")
        self.nb.add(self.goals_tab, text="  Goals  ")

        self._build_tasks_tab()
        self._build_goals_tab()

    # ── Tasks tab ─────────────────────────────────────────────────────────────
    def _build_tasks_tab(self) -> None:
        p = self._p
        outer = tk.Frame(self.tasks_tab, bg=p["bg"])
        outer.pack(fill="both", expand=True, padx=28, pady=20)

        # ── Input card
        card = tk.Frame(outer, bg=p["surface"],
                        highlightthickness=1, highlightbackground=p["border"])
        card.pack(fill="x", pady=(0, 16))

        inner = tk.Frame(card, bg=p["surface"])
        inner.pack(fill="x", padx=18, pady=14)

        # Entry row
        row1 = tk.Frame(inner, bg=p["surface"])
        row1.pack(fill="x")

        self.task_text = tk.StringVar()
        self.task_entry = tk.Entry(row1, textvariable=self.task_text,
                                   bg=p["input_bg"], fg=p["input_fg"],
                                   insertbackground=p["input_fg"],
                                   relief="flat", font=("Helvetica", 11),
                                   highlightthickness=1,
                                   highlightbackground=p["border"])
        self.task_entry.pack(side="left", fill="x", expand=True, ipady=7)
        self.task_entry.bind("<Return>", lambda e: self.safe(self.add_daily_task))

        btn_add = marble_button(row1, "Add Task",  lambda: self.safe(self.add_daily_task), p)
        btn_add.pack(side="left", padx=(10, 0))
        btn_daily = marble_button(row1, "↻ Add Daily", lambda: self.safe(self.add_recurring_task), p)
        btn_daily.configure(fg=p["daily_fg"])
        btn_daily.pack(side="left", padx=(6, 0))

        # Due picker row
        row2 = tk.Frame(inner, bg=p["surface"])
        row2.pack(fill="x", pady=(10, 0))
        tk.Label(row2, text="Due", bg=p["surface"], fg=p["muted"],
                 font=("Helvetica", 10)).pack(side="left", padx=(0, 8))
        self.task_due = DuePicker(row2, p)
        self.task_due.frame.pack(side="left")
        tk.Label(row2, text="  (ignored for daily tasks)",
                 bg=p["surface"], fg=p["muted"],
                 font=("Helvetica", 9)).pack(side="left")

        # ── Action strip
        strip = tk.Frame(outer, bg=p["bg"])
        strip.pack(fill="x", pady=(0, 10))

        marble_button(strip, "✓  Mark Done",    lambda: self.safe(self.toggle_daily_done),  p).pack(side="left")
        marble_button(strip, "Delete",          lambda: self.safe(self.delete_daily_task),  p, small=True).pack(side="left", padx=(8, 0))
        danger_button(strip, "Clear Completed", lambda: self.safe(self.delete_daily_done),  p, small=True).pack(side="left", padx=(8, 0))

        # Legend
        tk.Label(strip, text="● Blue = daily  ● Gray = done",
                 bg=p["bg"], fg=p["muted"],
                 font=("Helvetica", 9)).pack(side="right")

        # ── Tree
        tree_frame = tk.Frame(outer, bg=p["surface"],
                              highlightthickness=1, highlightbackground=p["border"])
        tree_frame.pack(fill="both", expand=True)

        self.tasks_tree = ttk.Treeview(tree_frame, columns=("type", "due"),
                                        show="tree headings", selectmode="browse")
        self.tasks_tree.heading("#0",   text="Task",    anchor="w")
        self.tasks_tree.heading("type", text="Type",    anchor="center")
        self.tasks_tree.heading("due",  text="Due",     anchor="center")
        self.tasks_tree.column("#0",   width=420, stretch=True,  minwidth=200)
        self.tasks_tree.column("type", width=90,  stretch=False, anchor="center", minwidth=70)
        self.tasks_tree.column("due",  width=130, stretch=False, anchor="center", minwidth=100)

        self.tasks_tree.tag_configure("recurring", foreground=p["daily_fg"])
        self.tasks_tree.tag_configure("done",      foreground=p["done_fg"])

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                             command=self.tasks_tree.yview)
        self.tasks_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tasks_tree.pack(fill="both", expand=True)

        self._treeviews = getattr(self, "_treeviews", [])
        self._treeviews.append(self.tasks_tree)
        self._due_pickers = getattr(self, "_due_pickers", [])
        self._due_pickers.append(self.task_due)

    # ── Goals tab ─────────────────────────────────────────────────────────────
    def _build_goals_tab(self) -> None:
        p = self._p
        outer = tk.Frame(self.goals_tab, bg=p["bg"])
        outer.pack(fill="both", expand=True)

        # ── Paned: sidebar | detail
        paned = tk.PanedWindow(outer, orient="horizontal",
                               bg=p["border"], sashwidth=1,
                               sashrelief="flat", showhandle=False)
        paned.pack(fill="both", expand=True)

        # Sidebar
        self.sidebar_frame = tk.Frame(paned, bg=p["surface"],
                                      width=230)
        paned.add(self.sidebar_frame, minsize=180)

        # Detail
        self.right_frame = tk.Frame(paned, bg=p["bg"])
        paned.add(self.right_frame, minsize=400)

        self._build_sidebar(p)
        self._build_detail(p)

    def _build_sidebar(self, p) -> None:
        sb = self.sidebar_frame

        # New goal form
        form = tk.Frame(sb, bg=p["surface"])
        form.pack(fill="x", padx=14, pady=(16, 8))

        tk.Label(form, text="New Goal", bg=p["surface"], fg=p["muted"],
                 font=("Helvetica", 9, "bold")).pack(anchor="w", pady=(0, 6))

        self.goal_title = tk.StringVar()
        self.goal_entry = tk.Entry(form, textvariable=self.goal_title,
                                   bg=p["input_bg"], fg=p["input_fg"],
                                   insertbackground=p["input_fg"],
                                   relief="flat", font=("Helvetica", 10),
                                   highlightthickness=1,
                                   highlightbackground=p["border"])
        self.goal_entry.pack(fill="x", ipady=6)
        self.goal_entry.bind("<Return>", lambda e: self.safe(self.add_goal))

        due_row = tk.Frame(form, bg=p["surface"])
        due_row.pack(fill="x", pady=(8, 0))
        tk.Label(due_row, text="Due", bg=p["surface"], fg=p["muted"],
                 font=("Helvetica", 9)).pack(side="left", padx=(0, 6))
        self.goal_due = DuePicker(due_row, p)
        self.goal_due.frame.pack(side="left")

        marble_button(form, "+ Add Goal", lambda: self.safe(self.add_goal), p).pack(
            fill="x", pady=(10, 0))

        # Separator
        tk.Frame(sb, height=1, bg=p["border"]).pack(fill="x", padx=14, pady=8)

        # Goals list
        tk.Label(sb, text="YOUR GOALS", bg=p["surface"], fg=p["muted"],
                 font=("Helvetica", 8, "bold")).pack(anchor="w", padx=14, pady=(0, 4))

        self.goals_list = tk.Listbox(
            sb, exportselection=False,
            bg=p["surface"], fg=p["text"],
            selectbackground=p["select_bg"], selectforeground=p["select_fg"],
            relief="flat", bd=0, highlightthickness=0,
            font=("Helvetica", 11), activestyle="none",
        )
        self.goals_list.pack(fill="both", expand=True, padx=6)
        self.goals_list.bind("<<ListboxSelect>>", lambda _e: self.refresh_goal_details())

        danger_button(sb, "Delete Goal", lambda: self.safe(self.delete_goal), p, small=True).pack(
            fill="x", padx=14, pady=12)

        self._due_pickers.append(self.goal_due)

    def _build_detail(self, p) -> None:
        rf = self.right_frame

        # Heading
        self.goal_heading = tk.Label(rf, text="Select a goal →",
                                     bg=p["bg"], fg=p["text"],
                                     font=("Helvetica", 16, "bold"),
                                     anchor="w")
        self.goal_heading.pack(fill="x", padx=24, pady=(20, 2))

        self.goal_due_label = tk.Label(rf, text="",
                                       bg=p["bg"], fg=p["muted"],
                                       font=("Helvetica", 10), anchor="w")
        self.goal_due_label.pack(fill="x", padx=24, pady=(0, 8))

        tk.Frame(rf, height=1, bg=p["border"]).pack(fill="x", padx=24, pady=(0, 12))

        # Notes
        notes_label = tk.Label(rf, text="NOTES", bg=p["bg"], fg=p["muted"],
                                font=("Helvetica", 8, "bold"))
        notes_label.pack(anchor="w", padx=24)

        self.goal_notes = tk.Text(rf, height=3, wrap="word",
                                  bg=p["input_bg"], fg=p["input_fg"],
                                  insertbackground=p["input_fg"],
                                  relief="flat", bd=0,
                                  highlightthickness=1,
                                  highlightbackground=p["border"],
                                  font=("Helvetica", 10), padx=8, pady=6)
        self.goal_notes.pack(fill="x", padx=24, pady=(4, 0))

        marble_button(rf, "Save Notes", lambda: self.safe(self.save_goal_notes), p, small=True).pack(
            anchor="w", padx=24, pady=(6, 12))

        tk.Frame(rf, height=1, bg=p["border"]).pack(fill="x", padx=24, pady=(0, 12))

        # Add item
        add_label = tk.Label(rf, text="ADD ITEM", bg=p["bg"], fg=p["muted"],
                              font=("Helvetica", 8, "bold"))
        add_label.pack(anchor="w", padx=24)

        item_row = tk.Frame(rf, bg=p["bg"])
        item_row.pack(fill="x", padx=24, pady=(6, 0))

        self.parent_task = tk.StringVar()
        self.parent_task_combo = ttk.Combobox(item_row, textvariable=self.parent_task,
                                               state="readonly", width=22,
                                               style="Marble.TCombobox")
        self.parent_task_combo.pack(side="left")

        self.goal_item_text = tk.StringVar()
        self.goal_item_entry = tk.Entry(item_row, textvariable=self.goal_item_text,
                                        bg=p["input_bg"], fg=p["input_fg"],
                                        insertbackground=p["input_fg"],
                                        relief="flat", font=("Helvetica", 10),
                                        highlightthickness=1,
                                        highlightbackground=p["border"])
        self.goal_item_entry.pack(side="left", fill="x", expand=True, padx=8, ipady=6)
        self.goal_item_entry.bind("<Return>", lambda e: self.safe(self.add_goal_item))

        marble_button(item_row, "+ Add", lambda: self.safe(self.add_goal_item), p, small=True).pack(side="left")

        due_row2 = tk.Frame(rf, bg=p["bg"])
        due_row2.pack(fill="x", padx=24, pady=(8, 0))
        tk.Label(due_row2, text="Due", bg=p["bg"], fg=p["muted"],
                 font=("Helvetica", 9)).pack(side="left", padx=(0, 6))
        self.goal_item_due = DuePicker(due_row2, p)
        self.goal_item_due.frame.pack(side="left")

        tk.Label(rf, text="'No parent' = task   |   Select a task = subtask",
                 bg=p["bg"], fg=p["muted"], font=("Helvetica", 9)).pack(
            anchor="w", padx=24, pady=(6, 10))

        tk.Frame(rf, height=1, bg=p["border"]).pack(fill="x", padx=24, pady=(0, 10))

        # Item actions
        act = tk.Frame(rf, bg=p["bg"])
        act.pack(fill="x", padx=24, pady=(0, 10))
        marble_button(act, "✓  Toggle Done",   lambda: self.safe(self.toggle_goal_item),  p, small=True).pack(side="left")
        danger_button(act, "Delete Selected",  lambda: self.safe(self.delete_goal_item),  p, small=True).pack(side="left", padx=(8, 0))

        # Goal tree
        tree_wrap = tk.Frame(rf, bg=p["surface"],
                             highlightthickness=1, highlightbackground=p["border"])
        tree_wrap.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        self.goal_tree = ttk.Treeview(tree_wrap, columns=("due",),
                                       show="tree headings", selectmode="browse")
        self.goal_tree.heading("#0",  text="Tasks & Subtasks", anchor="w")
        self.goal_tree.heading("due", text="Due",              anchor="center")
        self.goal_tree.column("#0",  width=460, stretch=True,  minwidth=200)
        self.goal_tree.column("due", width=130, stretch=False, anchor="center", minwidth=100)

        self.goal_tree.tag_configure("done", foreground=p["done_fg"])

        vsb2 = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.goal_tree.yview)
        self.goal_tree.configure(yscrollcommand=vsb2.set)
        vsb2.pack(side="right", fill="y")
        self.goal_tree.pack(fill="both", expand=True)

        self._treeviews.append(self.goal_tree)
        self._due_pickers.append(self.goal_item_due)

    # ── Safe wrapper ──────────────────────────────────────────────────────────
    def safe(self, action) -> None:
        try:
            action()
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror("Error", str(exc))

    # ── Label helpers ─────────────────────────────────────────────────────────
    def format_task_label(self, task: TaskItem) -> str:
        prefix = "↻  " if task.recurring else "    "
        check  = "✓  " if task.done else "○  "
        return f"{prefix}{check}{task.text}"

    # ── Selection helpers ─────────────────────────────────────────────────────
    def selected_goal_index(self) -> Optional[int]:
        sel = self.goals_list.curselection()
        return sel[0] if sel else None

    def selected_daily_index(self) -> Optional[int]:
        sel = self.tasks_tree.selection()
        if not sel:
            return None
        iid = sel[0]
        if not iid.startswith("d-"):
            return None
        return int(iid.split("-")[1])

    def selected_goal_item(self) -> Optional[Tuple[str, int, Optional[int]]]:
        sel = self.goal_tree.selection()
        if not sel:
            return None
        iid = sel[0]
        if iid.startswith("t-"):
            return ("task", int(iid.split("-")[1]), None)
        if iid.startswith("s-"):
            _, ti, si = iid.split("-")
            return ("subtask", int(ti), int(si))
        return None

    # ── Refresh ───────────────────────────────────────────────────────────────
    def refresh_tasks(self) -> None:
        for iid in self.tasks_tree.get_children():
            self.tasks_tree.delete(iid)
        for idx, task in enumerate(self.tasks):
            type_label = "Daily" if task.recurring else "One-time"
            tags = []
            if task.recurring:
                tags.append("recurring")
            if task.done:
                tags.append("done")
            self.tasks_tree.insert(
                "", "end", iid=f"d-{idx}",
                text=self.format_task_label(task),
                values=(type_label, task.due_date),
                tags=tuple(tags),
            )

    def refresh_goals(self) -> None:
        selected = self.selected_goal_index()
        self.goals_list.delete(0, tk.END)
        for goal in self.goals:
            label = f"{goal.title}  ({goal.due_date})" if goal.due_date else goal.title
            self.goals_list.insert(tk.END, "  " + label)
        if self.goals:
            next_idx = selected if selected is not None and selected < len(self.goals) else 0
            self.goals_list.selection_set(next_idx)
        self.refresh_goal_details()

    def refresh_goal_details(self) -> None:
        idx = self.selected_goal_index()
        self.goal_notes.delete("1.0", tk.END)
        for iid in self.goal_tree.get_children():
            self.goal_tree.delete(iid)

        if idx is None:
            self.goal_heading.config(text="Select a goal →")
            self.goal_due_label.config(text="")
            self.parent_task_combo["values"] = ["No parent (Goal Task)"]
            self.parent_task.set("No parent (Goal Task)")
            return

        goal = self.goals[idx]
        self.goal_heading.config(text=goal.title)
        self.goal_due_label.config(text=f"Due {goal.due_date}" if goal.due_date else "No due date")
        self.goal_notes.insert(tk.END, goal.notes)

        dropdown_options = ["No parent (Goal Task)"]
        for task_idx, task in enumerate(goal.tasks):
            task_iid = f"t-{task_idx}"
            tags = ("done",) if task.done else ()
            self.goal_tree.insert("", "end", iid=task_iid,
                                  text=self.format_task_label(task),
                                  values=(task.due_date,), tags=tags)
            dropdown_options.append(f"{task_idx + 1}. {task.text}")
            for sub_idx, subtask in enumerate(task.subtasks):
                stags = ("done",) if subtask.done else ()
                self.goal_tree.insert(task_iid, "end",
                                      iid=f"s-{task_idx}-{sub_idx}",
                                      text=self.format_task_label(subtask),
                                      values=(subtask.due_date,), tags=stags)

        self.parent_task_combo["values"] = dropdown_options
        if self.parent_task.get() not in dropdown_options:
            self.parent_task.set(dropdown_options[0])

    # ── Task actions ──────────────────────────────────────────────────────────
    def add_daily_task(self) -> None:
        text = self.task_text.get().strip()
        if not text:
            return
        due = self.task_due.get_value()
        self.tasks.append(TaskItem(text=text, due_date=due, recurring=False))
        self.task_text.set("")
        self.task_due.clear()
        self.store.save()
        self.refresh_tasks()

    def add_recurring_task(self) -> None:
        text = self.task_text.get().strip()
        if not text:
            return
        self.tasks.append(TaskItem(text=text, due_date="", recurring=True))
        self.task_text.set("")
        self.task_due.clear()
        self.store.save()
        self.refresh_tasks()

    def toggle_daily_done(self) -> None:
        idx = self.selected_daily_index()
        if idx is None:
            return
        task = self.tasks[idx]
        task.done = not task.done
        if task.recurring:
            task.last_done_date = today_str() if task.done else ""
        self.store.save()
        self.refresh_tasks()

    def delete_daily_task(self) -> None:
        idx = self.selected_daily_index()
        if idx is None:
            return
        del self.tasks[idx]
        self.store.save()
        self.refresh_tasks()

    def delete_daily_done(self) -> None:
        self.tasks = [t for t in self.tasks if not (t.done and not t.recurring)]
        self.store.data["tasks"] = self.tasks
        self.store.save()
        self.refresh_tasks()

    # ── Goal actions ──────────────────────────────────────────────────────────
    def add_goal(self) -> None:
        title = self.goal_title.get().strip()
        if not title:
            return
        due = self.goal_due.get_value()
        self.goals.append(GoalItem(title=title, due_date=due))
        self.goal_title.set("")
        self.goal_due.clear()
        self.store.save()
        self.refresh_goals()
        self.goals_list.selection_clear(0, tk.END)
        self.goals_list.selection_set(len(self.goals) - 1)
        self.refresh_goal_details()

    def delete_goal(self) -> None:
        idx = self.selected_goal_index()
        if idx is None:
            return
        del self.goals[idx]
        self.store.save()
        self.refresh_goals()

    def save_goal_notes(self) -> None:
        idx = self.selected_goal_index()
        if idx is None:
            return
        self.goals[idx].notes = self.goal_notes.get("1.0", tk.END).strip()
        self.store.save()

    def add_goal_item(self) -> None:
        idx = self.selected_goal_index()
        if idx is None:
            messagebox.showinfo("Select Goal", "Please select a goal first.")
            return
        text = self.goal_item_text.get().strip()
        if not text:
            return
        due = self.goal_item_due.get_value()
        parent = self.parent_task.get().strip()
        if not parent or parent == "No parent (Goal Task)":
            self.goals[idx].tasks.append(TaskItem(text=text, due_date=due))
        else:
            parent_idx = int(parent.split(".")[0]) - 1
            if parent_idx < 0 or parent_idx >= len(self.goals[idx].tasks):
                messagebox.showwarning("Invalid Parent", "Choose a valid parent task.")
                return
            self.goals[idx].tasks[parent_idx].subtasks.append(TaskItem(text=text, due_date=due))
        self.goal_item_text.set("")
        self.goal_item_due.clear()
        self.store.save()
        self.refresh_goal_details()

    def toggle_goal_item(self) -> None:
        goal_idx = self.selected_goal_index()
        selected = self.selected_goal_item()
        if goal_idx is None or selected is None:
            return
        item_type, task_idx, sub_idx = selected
        if item_type == "task":
            t = self.goals[goal_idx].tasks[task_idx]
            t.done = not t.done
        else:
            s = self.goals[goal_idx].tasks[task_idx].subtasks[sub_idx]
            s.done = not s.done
        self.store.save()
        self.refresh_goal_details()

    def delete_goal_item(self) -> None:
        goal_idx = self.selected_goal_index()
        selected = self.selected_goal_item()
        if goal_idx is None or selected is None:
            return
        item_type, task_idx, sub_idx = selected
        if item_type == "task":
            del self.goals[goal_idx].tasks[task_idx]
        else:
            del self.goals[goal_idx].tasks[task_idx].subtasks[sub_idx]
        self.store.save()
        self.refresh_goal_details()


def main() -> None:
    root = tk.Tk()
    TrackerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
