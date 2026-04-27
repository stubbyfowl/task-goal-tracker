# Task & Goal Tracker (macOS + Linux)

A beginner-friendly desktop app for:

- Daily task checklists
- Goals with their own checklist items
- Progress tracking for both tasks and goals
- Automatic local saving

No external Python packages are required.

## 1) Make sure Python is installed

Most systems already include Python 3. If needed:

- macOS: install from [python.org](https://www.python.org/downloads/macos/) or `brew install python`
- Ubuntu/Debian: `sudo apt install python3 python3-tk`
- Fedora: `sudo dnf install python3 python3-tkinter`

## 2) Run the app

From this folder:

```bash
python3 app.py
```

## 3) How to use

- **Daily Tasks tab**
  - Add tasks
  - Optional due date with dropdowns (month/day/hour/minute)
  - Check them off
  - Remove completed tasks

- **Goals tab**
  - Create a goal with optional due date dropdowns
  - Add tasks under each goal
  - Optionally add subtasks by selecting a parent task from a dropdown
  - Toggle done/delete from the shared tree list

Your data is saved in your user data folder (not inside the app bundle).

Actually saved locations by OS:

- macOS: `~/Library/Application Support/TaskGoalTracker/tracker_data.json`
- Linux: `~/.local/share/TaskGoalTracker/tracker_data.json`

## 4) Build macOS app

### macOS `.app`

```bash
python3 -m pip install --user pyinstaller
python3 -m PyInstaller -y --windowed --name "Task Goal Tracker" app.py
```

Output:

- `dist/Task Goal Tracker.app`

### Build macOS `.dmg` installer

```bash
mkdir -p dist/dmg-src
rm -rf "dist/dmg-src/Task Goal Tracker.app" "dist/dmg-src/Applications"
cp -R "dist/Task Goal Tracker.app" "dist/dmg-src/"
ln -s /Applications "dist/dmg-src/Applications"
hdiutil create -volname "Task Goal Tracker" -srcfolder "dist/dmg-src" -ov -format UDZO "dist/TaskGoalTracker-Installer.dmg"
```

Output:

- `dist/TaskGoalTracker-Installer.dmg`

## 5) Put on GitHub

```bash
git init
git add .
git commit -m "Initial Task Goal Tracker app"
```

Then create an empty GitHub repo in the web UI and connect/push:

```bash
git remote add origin <your-repo-url>
git branch -M main
git push -u origin main
```

## Optional: create a quick launcher script (macOS/Linux)

Create `run.sh`:

```bash
#!/usr/bin/env bash
cd "$(dirname "$0")"
python3 app.py
```

Then run:

```bash
chmod +x run.sh
./run.sh
```
