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
    # If True, this task recurs daily and resets each new day
    recurring: bool = False
    # The date this recurring task was last marked done (YYYY-MM-DD)
    last_done_date: str = ""


@dataclass
class GoalItem:
    title: str
    notes: str = ""
    due_date: str = ""
    tasks: List[TaskItem] = field(default_factory=list)


class DuePicker:
    def __init__(self, parent: tk.Widget):
        self.frame = ttk.Frame(parent)
        self.month = tk.StringVar(value="--")
        self.day = tk.StringVar(value="--")
        self.hour = tk.StringVar(value="--")
        self.minute = tk.StringVar(value="--")

        months = ["--"] + [f"{i:02d}" for i in range(1, 13)]
        days = ["--"] + [f"{i:02d}" for i in range(1, 32)]
        hours = ["--"] + [f"{i:02d}" for i in range(0, 24)]
        minutes = ["--"] + [f"{i:02d}" for i in range(0, 60)]

        self._combo(self.month, months, 4).pack(side="left")
        ttk.Label(self.frame, text="/").pack(side="left", padx=2)
        self._combo(self.day, days, 4).pack(side="left")
        ttk.Label(self.frame, text=" ").pack(side="left", padx=2)
        self._combo(self.hour, hours, 4).pack(side="left")
        ttk.Label(self.frame, text=":").pack(side="left", padx=2)
        self._combo(self.minute, minutes, 4).pack(side="left")

    def _combo(self, var: tk.StringVar, values: List[str], width: int) -> ttk.Combobox:
        return ttk.Combobox(
            self.frame,
            textvariable=var,
            values=values,
            width=width,
            state="readonly",
        )

    def set_value(self, value: str) -> None:
        if not value:
            self.clear()
            return
        try:
            parsed = datetime.strptime(value, "%m-%d %H:%M")
            self.month.set(parsed.strftime("%m"))
            self.day.set(parsed.strftime("%d"))
            self.hour.set(parsed.strftime("%H"))
            self.minute.set(parsed.strftime("%M"))
        except ValueError:
            self.clear()

    def get_value(self) -> str:
        parts = [self.month.get(), self.day.get(), self.hour.get(), self.minute.get()]
        if any(part == "--" for part in parts):
            return ""
        mm, dd, hh, minute = parts
        dt = datetime.strptime(f"{mm}-{dd} {hh}:{minute}", "%m-%d %H:%M")
        return dt.strftime("%m-%d %H:%M")

    def clear(self) -> None:
        self.month.set("--")
        self.day.set("--")
        self.hour.set("--")
        self.minute.set("--")


class DataStore:
    def __init__(self, path: Path):
        self.path = path
        self.data = {"tasks": [], "goals": []}
        self.load()

    def _load_task(self, item: dict) -> TaskItem:
        subtasks_raw = item.get("subtasks", [])
        subtasks = [self._load_task(sub) for sub in subtasks_raw] if isinstance(subtasks_raw, list) else []
        return TaskItem(
            text=item.get("text", ""),
            done=bool(item.get("done", False)),
            due_date=item.get("due_date", ""),
            subtasks=subtasks,
            recurring=bool(item.get("recurring", False)),
            last_done_date=item.get("last_done_date", ""),
        )

    def load(self) -> None:
        if not self.path.exists():
            self.save()
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            tasks = [self._load_task(item) for item in raw.get("tasks", [])]

            goals = []
            for goal_raw in raw.get("goals", []):
                old_checklist = goal_raw.get("checklist", [])
                tasks_raw = goal_raw.get("tasks", old_checklist)
                goals.append(
                    GoalItem(
                        title=goal_raw.get("title", ""),
                        notes=goal_raw.get("notes", ""),
                        due_date=goal_raw.get("due_date", ""),
                        tasks=[self._load_task(task) for task in tasks_raw],
                    )
                )

            self.data = {"tasks": tasks, "goals": goals}
        except Exception:
            self.data = {"tasks": [], "goals": []}
            messagebox.showwarning("Data Warning", "Could not read saved data. Starting empty.")

    def save(self) -> None:
        serializable = {
            "tasks": [asdict(task) for task in self.data["tasks"]],
            "goals": [asdict(goal) for goal in self.data["goals"]],
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("Save Error", f"Could not save data:\n\n{exc}")


class TrackerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Task & Goal Tracker")
        self.root.geometry("1060x700")
        self.root.minsize(700, 520)

        self.store = DataStore(get_data_file())
        self.tasks: List[TaskItem] = self.store.data["tasks"]
        self.goals: List[GoalItem] = self.store.data["goals"]
        self.dark_mode = tk.BooleanVar(value=False)

        # Reset recurring tasks whose last_done_date is not today
        self._reset_recurring_tasks()

        self._configure_style()
        self._build_ui()
        self.refresh_tasks()
        self.refresh_goals()

    def _reset_recurring_tasks(self) -> None:
        """Mark recurring tasks as not-done if they were completed on a previous day."""
        today = today_str()
        changed = False
        for task in self.tasks:
            if task.recurring and task.done and task.last_done_date != today:
                task.done = False
                changed = True
        if changed:
            self.store.save()

    def _configure_style(self) -> None:
        self.style = ttk.Style(self.root)
        if "clam" in self.style.theme_names():
            self.style.theme_use("clam")
        self._apply_theme()

    def _apply_theme(self) -> None:
        is_dark = self.dark_mode.get()
        if is_dark:
            self.bg = "#000000"
            self.card_bg = "#0f0f0f"
            self.text = "#f3f4f6"
            self.muted = "#a1a1aa"
            self.border = "#27272a"
            self.select_bg = "#232323"
            self.select_fg = "#ffffff"
            self.input_bg = "#121212"
            self.input_fg = "#f3f4f6"
            self.recurring_fg = "#60a5fa"   # blue tint for recurring in dark
        else:
            self.bg = "#f4f6fa"
            self.card_bg = "#ffffff"
            self.text = "#1f2937"
            self.muted = "#667085"
            self.border = "#d0d7e2"
            self.select_bg = "#e5e7eb"
            self.select_fg = "#111827"
            self.input_bg = "#ffffff"
            self.input_fg = "#111827"
            self.recurring_fg = "#2563eb"   # blue tint for recurring in light

        self.root.configure(bg=self.bg)
        self.style.configure("TFrame", background=self.bg)
        self.style.configure("Card.TFrame", background=self.card_bg, relief="flat", borderwidth=0)
        self.style.configure("TLabel", background=self.bg, foreground=self.text, font=("Helvetica", 11))
        self.style.configure("Muted.TLabel", background=self.bg, foreground=self.muted, font=("Helvetica", 10))
        self.style.configure("Header.TLabel", background=self.bg, foreground=self.text, font=("Helvetica", 14, "bold"))
        self.style.configure("TButton", padding=(12, 8), font=("Helvetica", 10))
        self.style.configure("TEntry", padding=8)
        self.style.configure("TCombobox", padding=5)
        self.style.configure("TNotebook", background=self.bg, borderwidth=0)
        self.style.configure("TNotebook.Tab", padding=(18, 10), font=("Helvetica", 10, "bold"))
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", self.card_bg), ("!selected", self.bg)],
            foreground=[("selected", self.text), ("!selected", self.muted)],
        )
        self.style.configure("Treeview", rowheight=28, font=("Helvetica", 10), background=self.input_bg, foreground=self.input_fg, fieldbackground=self.input_bg)
        self.style.configure("Treeview.Heading", font=("Helvetica", 10, "bold"))
        self.style.map("Treeview", background=[("selected", self.select_bg)], foreground=[("selected", self.select_fg)])
        self._apply_widget_theme()

    def _apply_widget_theme(self) -> None:
        for name in ("goals_list", "goal_notes"):
            if not hasattr(self, name):
                continue
            widget = getattr(self, name)
            if isinstance(widget, tk.Listbox):
                widget.configure(
                    bg=self.input_bg,
                    fg=self.input_fg,
                    selectbackground=self.select_bg,
                    selectforeground=self.select_fg,
                    highlightthickness=1,
                    highlightbackground=self.border,
                    relief="flat",
                )
            if isinstance(widget, tk.Text):
                widget.configure(
                    bg=self.input_bg,
                    fg=self.input_fg,
                    insertbackground=self.input_fg,
                    highlightthickness=1,
                    highlightbackground=self.border,
                    relief="flat",
                )

    def toggle_dark_mode(self) -> None:
        self._apply_theme()

    def _build_ui(self) -> None:
        wrapper = ttk.Frame(self.root)
        wrapper.pack(fill="both", expand=True, padx=16, pady=16)

        top = ttk.Frame(wrapper)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="Task & Goal Tracker", style="Header.TLabel").pack(side="left")
        ttk.Label(top, text=datetime.now().strftime("%A, %b %d"), style="Muted.TLabel").pack(side="right")
        ttk.Checkbutton(top, text="Dark", variable=self.dark_mode, command=lambda: self.safe(self.toggle_dark_mode)).pack(side="right", padx=(0, 10))

        tabs = ttk.Notebook(wrapper)
        tabs.pack(fill="both", expand=True)

        self.tasks_tab = ttk.Frame(tabs)
        self.goals_tab = ttk.Frame(tabs)
        tabs.add(self.tasks_tab, text="Tasks")       # renamed from "Daily Tasks"
        tabs.add(self.goals_tab, text="Goals")

        self._build_tasks_tab()
        self._build_goals_tab()

    def _build_tasks_tab(self) -> None:
        card = ttk.Frame(self.tasks_tab, style="Card.TFrame")
        card.pack(fill="both", expand=True, padx=8, pady=8)

        form = ttk.Frame(card)
        form.pack(fill="x", padx=14, pady=14)

        first_row = ttk.Frame(form)
        first_row.pack(fill="x")
        self.task_text = tk.StringVar()
        ttk.Entry(first_row, textvariable=self.task_text).pack(side="left", fill="x", expand=True)
        ttk.Button(first_row, text="Add Task", command=lambda: self.safe(self.add_daily_task)).pack(side="left", padx=(8, 0))
        ttk.Button(first_row, text="Add Daily", command=lambda: self.safe(self.add_recurring_task)).pack(side="left", padx=(6, 0))

        second_row = ttk.Frame(form)
        second_row.pack(fill="x", pady=(8, 0))
        self.task_due = DuePicker(second_row)
        self.task_due.frame.pack(side="left")
        ttk.Label(second_row, text="  (Due date ignored for daily tasks)", style="Muted.TLabel").pack(side="left")

        actions = ttk.Frame(card)
        actions.pack(fill="x", padx=14, pady=(0, 8))
        ttk.Button(actions, text="Toggle Done", command=lambda: self.safe(self.toggle_daily_done)).pack(side="left")
        ttk.Button(actions, text="Delete", command=lambda: self.safe(self.delete_daily_task)).pack(side="left", padx=8)
        ttk.Button(actions, text="Delete Completed", command=lambda: self.safe(self.delete_daily_done)).pack(side="left", padx=8)

        self.tasks_tree = ttk.Treeview(card, columns=("type", "due"), show="tree headings", selectmode="browse")
        self.tasks_tree.heading("#0", text="Task")
        self.tasks_tree.heading("type", text="Type")
        self.tasks_tree.heading("due", text="Due")
        self.tasks_tree.column("#0", width=380, stretch=True)
        self.tasks_tree.column("type", width=80, minwidth=70, stretch=False, anchor="center")
        self.tasks_tree.column("due", width=130, minwidth=110, stretch=False, anchor="center")

        # Tag for recurring/daily tasks — blue foreground
        self.tasks_tree.tag_configure("recurring", foreground="#2563eb")

        self.tasks_tree.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        # Legend
        legend = ttk.Frame(card)
        legend.pack(fill="x", padx=14, pady=(0, 8))
        ttk.Label(legend, text="● Blue = Daily task (resets each day)  ● Normal = One-time task", style="Muted.TLabel").pack(side="left")

    def _build_goals_tab(self) -> None:
        outer = ttk.Panedwindow(self.goals_tab, orient="horizontal")
        outer.pack(fill="both", expand=True, padx=8, pady=8)

        left = ttk.Frame(outer, style="Card.TFrame")
        right = ttk.Frame(outer, style="Card.TFrame")
        outer.add(left, weight=1)
        outer.add(right, weight=3)

        goal_form = ttk.Frame(left)
        goal_form.pack(fill="x", padx=12, pady=12)
        self.goal_title = tk.StringVar()
        ttk.Entry(goal_form, textvariable=self.goal_title, width=24).pack(fill="x")
        self.goal_due = DuePicker(goal_form)
        self.goal_due.frame.pack(fill="x", pady=(6, 0))
        ttk.Button(goal_form, text="Add Goal", command=lambda: self.safe(self.add_goal)).pack(fill="x", pady=(8, 0))

        self.goals_list = tk.Listbox(left, exportselection=False, height=16, relief="flat", bd=0)
        self.goals_list.pack(fill="both", expand=True, padx=12)
        self.goals_list.bind("<<ListboxSelect>>", lambda _e: self.refresh_goal_details())

        ttk.Button(left, text="Delete Goal", command=lambda: self.safe(self.delete_goal)).pack(fill="x", padx=12, pady=12)

        self.goal_heading = ttk.Label(right, text="Select a goal", style="Header.TLabel")
        self.goal_heading.pack(anchor="w", padx=14, pady=(12, 6))

        self.goal_notes = tk.Text(right, height=4, wrap="word", relief="flat", bd=1)
        self.goal_notes.pack(fill="x", padx=14)
        ttk.Button(right, text="Save Notes", command=lambda: self.safe(self.save_goal_notes)).pack(anchor="w", padx=14, pady=6)

        item_row = ttk.Frame(right)
        item_row.pack(fill="x", padx=14, pady=(8, 4))
        item_top = ttk.Frame(item_row)
        item_top.pack(fill="x")
        self.parent_task = tk.StringVar()
        self.parent_task_combo = ttk.Combobox(item_top, textvariable=self.parent_task, state="readonly", width=24)
        self.parent_task_combo.pack(side="left")
        self.goal_item_text = tk.StringVar()
        ttk.Entry(item_top, textvariable=self.goal_item_text).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(item_top, text="Add Item", command=lambda: self.safe(self.add_goal_item)).pack(side="left")
        item_bottom = ttk.Frame(item_row)
        item_bottom.pack(fill="x", pady=(6, 0))
        self.goal_item_due = DuePicker(item_bottom)
        self.goal_item_due.frame.pack(side="left")
        ttk.Label(
            right,
            text="Parent dropdown: 'No parent' adds a task; choose a task to add a subtask.",
            style="Muted.TLabel",
        ).pack(anchor="w", padx=14, pady=(0, 6))

        actions = ttk.Frame(right)
        actions.pack(fill="x", padx=14, pady=(0, 8))
        ttk.Button(actions, text="Toggle Done", command=lambda: self.safe(self.toggle_goal_item)).pack(side="left")
        ttk.Button(actions, text="Delete Selected", command=lambda: self.safe(self.delete_goal_item)).pack(side="left", padx=8)

        self.goal_tree = ttk.Treeview(right, columns=("due",), show="tree headings", selectmode="browse")
        self.goal_tree.heading("#0", text="Goal Tasks and Subtasks")
        self.goal_tree.heading("due", text="Due")
        self.goal_tree.column("#0", width=460, stretch=True)
        self.goal_tree.column("due", width=130, minwidth=110, stretch=False, anchor="center")
        self.goal_tree.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self._apply_widget_theme()

    def safe(self, action) -> None:
        try:
            action()
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror("Unexpected Error", str(exc))

    def format_task_label(self, task: TaskItem) -> str:
        prefix = "↻ " if task.recurring else ""
        return f"{prefix}[{'x' if task.done else ' '}] {task.text}"

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
            _, task_idx, sub_idx = iid.split("-")
            return ("subtask", int(task_idx), int(sub_idx))
        return None

    def refresh_tasks(self) -> None:
        for iid in self.tasks_tree.get_children():
            self.tasks_tree.delete(iid)
        for idx, task in enumerate(self.tasks):
            type_label = "Daily" if task.recurring else "One-time"
            tags = ("recurring",) if task.recurring else ()
            self.tasks_tree.insert(
                "", "end",
                iid=f"d-{idx}",
                text=self.format_task_label(task),
                values=(type_label, task.due_date),
                tags=tags,
            )

    def refresh_goals(self) -> None:
        selected = self.selected_goal_index()
        self.goals_list.delete(0, tk.END)
        for goal in self.goals:
            label = f"{goal.title} ({goal.due_date})" if goal.due_date else goal.title
            self.goals_list.insert(tk.END, label)
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
            self.goal_heading.config(text="Select a goal")
            self.parent_task_combo["values"] = ["No parent (Goal Task)"]
            self.parent_task.set("No parent (Goal Task)")
            return

        goal = self.goals[idx]
        heading = f"{goal.title} ({goal.due_date})" if goal.due_date else goal.title
        self.goal_heading.config(text=heading)
        self.goal_notes.insert(tk.END, goal.notes)

        dropdown_options = ["No parent (Goal Task)"]
        for task_idx, task in enumerate(goal.tasks):
            task_iid = f"t-{task_idx}"
            self.goal_tree.insert("", "end", iid=task_iid, text=self.format_task_label(task), values=(task.due_date,))
            dropdown_options.append(f"{task_idx + 1}. {task.text}")
            for sub_idx, subtask in enumerate(task.subtasks):
                self.goal_tree.insert(task_iid, "end", iid=f"s-{task_idx}-{sub_idx}", text=self.format_task_label(subtask), values=(subtask.due_date,))

        self.parent_task_combo["values"] = dropdown_options
        if self.parent_task.get() not in dropdown_options:
            self.parent_task.set(dropdown_options[0])

    def add_daily_task(self) -> None:
        """Add a regular one-time task."""
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
        """Add a daily recurring task (ignores due date picker)."""
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
        # For recurring tasks, record the date it was completed
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
        # Only delete completed one-time tasks; leave recurring tasks alone
        self.tasks = [task for task in self.tasks if not (task.done and not task.recurring)]
        self.store.data["tasks"] = self.tasks
        self.store.save()
        self.refresh_tasks()

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
                messagebox.showwarning("Invalid Parent", "Please choose a valid parent task.")
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
            task = self.goals[goal_idx].tasks[task_idx]
            task.done = not task.done
        else:
            subtask = self.goals[goal_idx].tasks[task_idx].subtasks[sub_idx]
            subtask.done = not subtask.done
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
