import os
import shutil
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

# ── Category definitions ──────────────────────────────────────────────────────
CATEGORIES = {
    "Documents":       [".pdf", ".docx", ".doc", ".txt", ".xlsx", ".xls",
                        ".pptx", ".ppt", ".csv", ".odt", ".rtf", ".md"],
    "Images":          [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg",
                        ".webp", ".ico", ".tiff", ".tif", ".raw", ".heic"],
    "Videos":          [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv",
                        ".webm", ".m4v", ".mpeg", ".mpg", ".3gp"],
    "Audio":           [".mp3", ".wav", ".aac", ".flac", ".ogg", ".wma",
                        ".m4a", ".opus", ".aiff"],
    "Archives":        [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
                        ".xz", ".tar.gz", ".tar.bz2"],
    "Programs & Code": [".py", ".java", ".c", ".cpp", ".h", ".js", ".ts",
                        ".html", ".css", ".php", ".rb", ".go", ".rs",
                        ".swift", ".kt", ".sh", ".bat", ".exe", ".msi",
                        ".dmg", ".deb", ".rpm", ".json", ".xml", ".yaml",
                        ".yml", ".sql"],
}

CAT_ICONS = {
    "Documents": "📄", "Images": "🖼️", "Videos": "🎥",
    "Audio": "🎵", "Archives": "🗜️", "Programs & Code": "💻", "Others": "📚",
}

CAT_COLORS = {
    "Documents":       "#3B82F6",
    "Images":          "#EC4899",
    "Videos":          "#8B5CF6",
    "Audio":           "#F59E0B",
    "Archives":        "#10B981",
    "Programs & Code": "#EF4444",
    "Others":          "#6B7280",
}


def get_category(ext: str) -> str:
    ext = ext.lower()
    for cat, exts in CATEGORIES.items():
        if ext in exts:
            return cat
    return "Others"


# category folder names — used to skip them during recursive walk
CAT_FOLDER_NAMES = set(CATEGORIES.keys()) | {"Others"}


def list_files(folder: str, recursive: bool = False) -> list[dict]:
    """Return a list of {name, subdir, ext, category} for every file in folder."""
    root = Path(folder)
    result = []
    if recursive:
        for dirpath, dirnames, filenames in os.walk(folder):
            # Skip the category folders we create at the top level
            dirnames[:] = [
                d for d in dirnames
                if not (Path(dirpath) == root and d in CAT_FOLDER_NAMES)
            ]
            for fname in filenames:
                item = Path(dirpath) / fname
                ext  = item.suffix
                rel  = str(item.relative_to(root).parent)
                result.append({
                    "name":   fname,
                    "subdir": "" if rel == "." else rel,
                    "ext":    ext if ext else "(none)",
                    "cat":    get_category(ext),
                })
    else:
        for item in root.iterdir():
            if item.is_dir():
                continue
            ext = item.suffix
            result.append({
                "name":   item.name,
                "subdir": "",
                "ext":    ext if ext else "(none)",
                "cat":    get_category(ext),
            })
    result.sort(key=lambda x: (x["cat"], x["subdir"], x["name"].lower()))
    return result


def safe_dest(dest):
    """Return a non-colliding Path by appending (1), (2), … to the stem."""
    if not dest.exists():
        return dest
    stem, suffix, parent = dest.stem, dest.suffix, dest.parent
    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def sort_files(folder: str, recursive: bool = False) -> dict:
    """Move files into category sub-folders at *folder*.

    If *recursive* is True, os.walk() descends into every sub-folder
    (skipping the category folders we create at the top level) and moves
    all discovered files up into the top-level category folders.
    """
    root = Path(folder)
    counts = {cat: 0 for cat in list(CATEGORIES.keys()) + ["Others"]}
    folders_created = set()
    file_log = []
    renamed_count = 0
    start = time.perf_counter()

    if recursive:
        # Collect (file_path, relative_subfolder) for every file we will move,
        # before we start moving so the walk isn't confused by mid-walk changes.
        to_move = []
        for dirpath, dirnames, filenames in os.walk(str(root)):
            cur = Path(dirpath)
            # At the top level skip our own output category folders
            if cur == root:
                dirnames[:] = [d for d in dirnames if d not in CAT_FOLDER_NAMES]
            rel = str(cur.relative_to(root))
            for fname in filenames:
                to_move.append((cur / fname, "" if rel == "." else rel))
    else:
        to_move = [
            (item, "")
            for item in root.iterdir()
            if item.is_file()
        ]

    for item, subdir in to_move:
        if not item.exists():          # already moved by a previous iteration
            continue
        ext = item.suffix
        cat = get_category(ext)
        dest_dir = root / cat
        dest_dir.mkdir(exist_ok=True)
        folders_created.add(cat)

        dest = safe_dest(dest_dir / item.name)
        renamed = dest.name != item.name
        if renamed:
            renamed_count += 1

        shutil.move(str(item), str(dest))
        counts[cat] += 1
        file_log.append({
            "original": item.name,
            "saved_as": dest.name,
            "subdir":   subdir,
            "cat":      cat,
            "renamed":  renamed,
        })

    # Remove empty sub-directories left behind by recursive sort
    if recursive:
        for dirpath, dirnames, filenames in os.walk(str(root), topdown=False):
            cur = Path(dirpath)
            if cur == root:
                continue
            if cur.name in CAT_FOLDER_NAMES:
                continue
            try:
                cur.rmdir()          # only succeeds if empty
            except OSError:
                pass

    elapsed = time.perf_counter() - start
    return {
        "counts":          counts,
        "folders_created": len(folders_created),
        "total_files":     sum(counts.values()),
        "renamed_count":   renamed_count,
        "elapsed":         elapsed,
        "file_log":        file_log,
        "recursive":       recursive,
    }


# ── GUI ───────────────────────────────────────────────────────────────────────
class FileSorterApp(tk.Tk):
    BG       = "#F0F2F5"
    CARD     = "#FFFFFF"
    ACCENT   = "#5B5BD6"
    ACCENT_H = "#4747C2"
    TEXT     = "#1A1A2E"
    MUTED    = "#6B7280"
    MONO     = ("Courier New", 10)

    def __init__(self):
        super().__init__()
        self.title("Auto File Sorter")
        self.resizable(True, True)
        self.configure(bg=self.BG)
        self._center(720, 780)
        self._last_result = None
        self._current_folder = None
        self._build_ui()

    # ── build ─────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # header
        hdr = tk.Frame(self, bg=self.ACCENT, padx=24, pady=16)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🗂  Auto File Sorter", font=("Helvetica", 18, "bold"),
                 bg=self.ACCENT, fg="#FFFFFF").pack(anchor="w")
        tk.Label(hdr, text="Organise your folder in one click",
                 font=("Helvetica", 10), bg=self.ACCENT, fg="#C7C7F4").pack(anchor="w")

        # folder picker
        pick = tk.Frame(self, bg=self.CARD, padx=20, pady=14,
                        highlightthickness=1, highlightbackground="#D1D5DB")
        pick.pack(fill="x", padx=20, pady=(16, 6))
        tk.Label(pick, text="Select Folder", font=("Helvetica", 11, "bold"),
                 bg=self.CARD, fg=self.TEXT).pack(anchor="w")
        tk.Label(pick, text="Choose the folder whose files you want to sort.",
                 font=("Helvetica", 9), bg=self.CARD, fg=self.MUTED).pack(anchor="w", pady=(2, 8))

        row = tk.Frame(pick, bg=self.CARD)
        row.pack(fill="x")
        self.path_var = tk.StringVar(value="No folder selected")
        tk.Label(row, textvariable=self.path_var, font=("Helvetica", 9),
                 bg="#F9FAFB", fg=self.TEXT, anchor="w", padx=8, pady=6,
                 highlightthickness=1, highlightbackground="#D1D5DB",
                 width=52).pack(side="left", fill="x", expand=True)
        tk.Button(row, text="Browse", command=self._browse,
                  bg=self.ACCENT, fg="white", font=("Helvetica", 9, "bold"),
                  relief="flat", padx=14, pady=6, cursor="hand2",
                  activebackground=self.ACCENT_H, activeforeground="white",
                  bd=0).pack(side="left", padx=(8, 0))

        # ── recursive toggle ──
        self.recursive_var = tk.BooleanVar(value=False)
        rec_row = tk.Frame(pick, bg=self.CARD)
        rec_row.pack(anchor="w", pady=(8, 0))
        tk.Checkbutton(rec_row, text="Include sub-folders (recursive sort)",
                       variable=self.recursive_var,
                       command=self._on_recursive_toggle,
                       font=("Helvetica", 9), bg=self.CARD, fg=self.TEXT,
                       activebackground=self.CARD, selectcolor=self.CARD,
                       cursor="hand2").pack(side="left")
        tk.Label(rec_row, text="⚠ moves ALL nested files to top-level category folders",
                 font=("Helvetica", 8), bg=self.CARD, fg="#F59E0B").pack(side="left", padx=(6, 0))

        # ── file list (shown after Browse) ──
        list_outer = tk.Frame(self, bg=self.BG, padx=20)
        list_outer.pack(fill="both", expand=True, pady=(4, 4))

        hrow = tk.Frame(list_outer, bg=self.BG)
        hrow.pack(fill="x", pady=(4, 4))
        tk.Label(hrow, text="Files in Folder", font=("Helvetica", 10, "bold"),
                 bg=self.BG, fg=self.TEXT).pack(side="left")
        self.file_count_var = tk.StringVar(value="")
        tk.Label(hrow, textvariable=self.file_count_var, font=("Helvetica", 9),
                 bg=self.BG, fg=self.MUTED).pack(side="left", padx=8)

        # Treeview with scrollbar
        tree_frame = tk.Frame(list_outer, bg=self.CARD,
                              highlightthickness=1, highlightbackground="#D1D5DB")
        tree_frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Files.Treeview",
                        background=self.CARD, fieldbackground=self.CARD,
                        foreground=self.TEXT, rowheight=26,
                        font=("Helvetica", 9))
        style.configure("Files.Treeview.Heading",
                        background="#EEF0FF", foreground=self.ACCENT,
                        font=("Helvetica", 9, "bold"), relief="flat")
        style.map("Files.Treeview", background=[("selected", "#EEF0FF")],
                  foreground=[("selected", self.ACCENT)])

        cols = ("filename", "subdir", "ext", "category")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                  style="Files.Treeview", selectmode="browse")
        self.tree.heading("filename", text="File Name")
        self.tree.heading("subdir",   text="Sub-folder")
        self.tree.heading("ext",      text="Extension")
        self.tree.heading("category", text="Category")
        self.tree.column("filename", width=240, anchor="w")
        self.tree.column("subdir",   width=120, anchor="w")
        self.tree.column("ext",      width=70,  anchor="center")
        self.tree.column("category", width=150, anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # ── action buttons row ──
        btn_row = tk.Frame(self, bg=self.BG, padx=20, pady=6)
        btn_row.pack(fill="x")

        self.sort_btn = tk.Button(btn_row, text="⚡  Sort Files",
                                  command=self._sort,
                                  bg=self.ACCENT, fg="white",
                                  font=("Helvetica", 11, "bold"),
                                  relief="flat", pady=10, cursor="hand2",
                                  activebackground=self.ACCENT_H,
                                  activeforeground="white", bd=0)
        self.sort_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.report_btn = tk.Button(btn_row, text="📋  Summary Report",
                                    command=self._show_summary_window,
                                    bg="#22C55E", fg="white",
                                    font=("Helvetica", 11, "bold"),
                                    relief="flat", pady=10, cursor="hand2",
                                    activebackground="#16A34A",
                                    activeforeground="white", bd=0,
                                    state="disabled")
        self.report_btn.pack(side="left", fill="x", expand=True)

        # status
        self.status_var = tk.StringVar(value="Ready — select a folder to begin.")
        tk.Label(self, textvariable=self.status_var, font=("Helvetica", 9),
                 bg=self.BG, fg=self.MUTED, anchor="w",
                 padx=20, pady=6).pack(fill="x", side="bottom")

    # ── actions ───────────────────────────────────────────────────────────────
    def _browse(self):
        folder = filedialog.askdirectory(title="Select a folder to sort")
        if not folder:
            return
        self.path_var.set(folder)
        self._current_folder = folder
        self._load_file_list(folder)
        self.status_var.set(f"Folder selected: {folder}")
        self._last_result = None
        self.report_btn.config(state="normal")

    def _load_file_list(self, folder: str):
        """Scan folder and populate the treeview with file → category info."""
        self.tree.delete(*self.tree.get_children())
        recursive = getattr(self, "recursive_var", None) and self.recursive_var.get()
        files = list_files(folder, recursive=recursive)
        self.file_count_var.set(
            f"({len(files)} file{'s' if len(files)!=1 else ''}"
            f"{'  •  recursive' if recursive else ''})"
        )
        for f in files:
            icon = CAT_ICONS.get(f["cat"], "📁")
            self.tree.insert("", "end",
                             values=(f["name"], f.get("subdir", ""), f["ext"], f"{icon} {f['cat']}"))
        # color-code rows by category tag
        for child in self.tree.get_children():
            cat_cell = self.tree.item(child, "values")[3]
            for cat in list(CATEGORIES.keys()) + ["Others"]:
                if cat in cat_cell:
                    tag = cat.replace(" ", "_").replace("&", "n")
                    self.tree.item(child, tags=(tag,))
                    color = CAT_COLORS.get(cat, "#6B7280")
                    self.tree.tag_configure(tag, foreground=color)
                    break

    def _sort(self):
        folder = self.path_var.get()
        if folder == "No folder selected" or not os.path.isdir(folder):
            messagebox.showwarning("No Folder", "Please select a valid folder first.")
            return
        recursive = self.recursive_var.get()
        scope = "ALL files including those in sub-folders" if recursive else "Files"
        if not messagebox.askyesno("Confirm Sort",
                f"{scope} in:\n{folder}\nwill be moved into top-level category folders.\n\nContinue?"):
            return

        self.sort_btn.config(state="disabled", text="Sorting…")
        self.update()

        recursive = self.recursive_var.get()
        try:
            result = sort_files(folder, recursive=recursive)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.sort_btn.config(state="normal", text="⚡  Sort Files")
            return

        self._last_result = result
        self.sort_btn.config(state="normal", text="⚡  Sort Files")
        self.report_btn.config(state="normal")
        rn = result.get('renamed_count', 0)
        rename_note = f'  ({rn} duplicate{"s" if rn!=1 else ""} renamed)' if rn else ''
        self.status_var.set(
            f"Done — {result['total_files']} files sorted in {result['elapsed']:.2f}s{rename_note}.  "
            "Click 'Summary Report' to view details.")
        # refresh list (now mostly empty / moved)
        self._load_file_list(folder)

    def _on_recursive_toggle(self):
        """Refresh the file list when the recursive checkbox changes."""
        folder = self.path_var.get()
        if folder and folder != "No folder selected" and os.path.isdir(folder):
            self._load_file_list(folder)

    def _show_summary_window(self):
        folder = getattr(self, "_current_folder", None) or self.path_var.get()
        if not folder or folder == "No folder selected":
            messagebox.showwarning("No Folder", "Please select a folder first.")
            return

        # If we have sort results use them; otherwise build a preview from current files
        if self._last_result:
            r        = self._last_result
            counts   = r["counts"]
            n_folders = r["folders_created"]
            total    = r["total_files"]
            elapsed  = r["elapsed"]
            file_log = r.get("file_log", [])
            mode     = "POST-SORT"
        else:
            files = list_files(folder)
            counts = {cat: 0 for cat in list(CATEGORIES.keys()) + ["Others"]}
            file_log = []
            for f in files:
                counts[f["cat"]] += 1
                file_log.append({"name": f["name"], "cat": f["cat"]})
            total    = len(files)
            n_folders = 0
            elapsed  = 0.0
            mode     = "PREVIEW (not sorted yet)"

        win = tk.Toplevel(self)
        win.title("Sorting Summary Report")
        win.configure(bg=self.BG)
        win.resizable(True, True)
        self._center_win(win, 560, 620)

        # header
        hdr = tk.Frame(win, bg=self.ACCENT, padx=20, pady=14)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"📋  Sorting Summary Report  [{mode}]",
                 font=("Helvetica", 14, "bold"),
                 bg=self.ACCENT, fg="white").pack(anchor="w")

        # scrollable text area
        body = tk.Frame(win, bg=self.CARD, padx=18, pady=14,
                        highlightthickness=1, highlightbackground="#D1D5DB")
        body.pack(fill="both", expand=True, padx=16, pady=12)

        txt = tk.Text(body, font=("Courier New", 10), bg=self.CARD, fg=self.TEXT,
                      relief="flat", wrap="none", state="normal",
                      selectbackground=self.ACCENT)
        vsb = ttk.Scrollbar(body, orient="vertical",   command=txt.yview)
        hsb = ttk.Scrollbar(body, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right",  fill="y")
        hsb.pack(side="bottom", fill="x")
        txt.pack(fill="both", expand=True)

        # build report text
        W = 52
        lines = [
            "=" * W,
            f"{'SORTING SUMMARY REPORT':^{W}}",
            "=" * W,
            "",
            f"  {'Category':<20} {'Files':>6}",
            f"  {'-'*20} {'-'*6}",
        ]
        for cat, n in counts.items():
            icon = CAT_ICONS.get(cat, "📁")
            lines.append(f"  {icon+' '+cat:<20} {n:>6}")
        renamed   = r.get("renamed_count", 0) if self._last_result else 0
        rec_label = "Yes" if (self._last_result and self._last_result.get("recursive")) else "No"
        lines += [
            "",
            "-" * W,
            f"  Total Files       : {total}",
            f"  Folders Created   : {n_folders}",
            f"  Duplicates Renamed: {renamed}",
            f"  Recursive Sort    : {rec_label}",
            f"  Time Taken        : {elapsed:.2f} sec",
            "=" * W,
        ]

        if file_log:
            lines += [
                "",
                f"{'FILE DETAILS':^{W}}",
                "-" * W,
                f"  {'File Name':<34} {'Category':<16}",
                f"  {'-'*34} {'-'*16}",
            ]
            for f in sorted(file_log, key=lambda x: (x["cat"], x.get("subdir",""), x.get("original", x.get("name","")).lower())):
                icon = CAT_ICONS.get(f["cat"], "📁")
                orig = f.get("original", f.get("name", ""))
                saved = f.get("saved_as", orig)
                subdir = f.get("subdir", "")
                prefix = f"[{subdir}] " if subdir else ""
                display = prefix + orig
                display = display[:30] + ".." if len(display) > 32 else display
                rename_mark = f" → {saved}" if f.get("renamed") else ""
                lines.append(f"  {display:<32} {icon} {f['cat']}{rename_mark}")
            lines.append("=" * W)

        txt.insert("end", "\n".join(lines))
        txt.config(state="disabled")

        # close button
        tk.Button(win, text="Close", command=win.destroy,
                  bg=self.ACCENT, fg="white", font=("Helvetica", 10, "bold"),
                  relief="flat", pady=8, cursor="hand2",
                  activebackground=self.ACCENT_H, bd=0
                  ).pack(fill="x", padx=16, pady=(0, 12))

    # ── helpers ───────────────────────────────────────────────────────────────
    def _center(self, w, h):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _center_win(self, win, w, h):
        win.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")


if __name__ == "__main__":
    app = FileSorterApp()
    app.mainloop()
