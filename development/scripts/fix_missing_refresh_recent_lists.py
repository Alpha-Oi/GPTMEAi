from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Development GPTMEAi")
TARGET = PROJECT_ROOT / "chat_migration_collector.py"
BACKUP_DIR = PROJECT_ROOT / ".gptcollector" / "backups"

PATCH_BLOCK = '''
    def _refresh_recent_lists(self) -> None:
        if not hasattr(self, "exports_listbox") or not hasattr(self, "snapshots_listbox"):
            return

        self.exports_listbox.delete(0, tk.END)
        self.snapshots_listbox.delete(0, tk.END)

        self._recent_export_paths = []
        self._recent_snapshot_paths = []

        export_paths = sorted(self.collector.exports_dir.glob("migration_block_*.txt"), reverse=True)[:10]
        snapshot_paths = sorted(self.collector.snapshots_dir.glob("snapshot_*.json"), reverse=True)[:10]

        for path in export_paths:
            self._recent_export_paths.append(path)
            self.exports_listbox.insert(tk.END, path.name)

        for path in snapshot_paths:
            self._recent_snapshot_paths.append(path)
            self.snapshots_listbox.insert(tk.END, path.name)

    def _open_selected_export(self) -> None:
        if not hasattr(self, "_recent_export_paths"):
            self._refresh_recent_lists()

        sel = self.exports_listbox.curselection()
        if not sel:
            if messagebox:
                messagebox.showinfo("Export", "Сначала выбери export из списка.")
            return

        path = self._recent_export_paths[sel[0]]
        try:
            if hasattr(self.collector, "_open_path_in_system"):
                self.collector._open_path_in_system(path)
            elif hasattr(Path, "open"):
                import os
                if os.name == "nt" and hasattr(os, "startfile"):
                    os.startfile(str(path))
        except Exception:
            pass

        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, "Открыт export:\\n" + path.as_posix())

    def _open_selected_snapshot(self) -> None:
        if not hasattr(self, "_recent_snapshot_paths"):
            self._refresh_recent_lists()

        sel = self.snapshots_listbox.curselection()
        if not sel:
            if messagebox:
                messagebox.showinfo("Snapshot", "Сначала выбери snapshot из списка.")
            return

        path = self._recent_snapshot_paths[sel[0]]
        try:
            if hasattr(self.collector, "_open_path_in_system"):
                self.collector._open_path_in_system(path)
            elif hasattr(Path, "open"):
                import os
                if os.name == "nt" and hasattr(os, "startfile"):
                    os.startfile(str(path))
        except Exception:
            pass

        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, "Открыт snapshot:\\n" + path.as_posix())

    def _on_export_double_click(self, _event=None) -> None:
        self._open_selected_export()

    def _on_snapshot_double_click(self, _event=None) -> None:
        self._open_selected_snapshot()

'''.strip("\n")


def backup_file(path: Path) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = BACKUP_DIR / f"{path.name}.fix_recent_lists_{stamp}.bak"
    shutil.copy2(path, dst)
    print(f"[OK] Backup created: {dst}")


def main() -> int:
    if not TARGET.exists():
        print(f"[ERROR] File not found: {TARGET}")
        return 1

    backup_file(TARGET)

    text = TARGET.read_text(encoding="utf-8", errors="ignore")
    original = text

    if "def _refresh_recent_lists(self) -> None:" in text:
        print("[OK] Method _refresh_recent_lists already exists. No patch needed.")
    else:
        marker = "    def _load_state(self) -> None:\n"
        if marker not in text:
            print("[ERROR] Could not find insertion point for CollectorGUI methods.")
            return 1

        text = text.replace(marker, PATCH_BLOCK + "\n\n" + marker, 1)

    TARGET.write_text(text, encoding="utf-8", newline="\n")

    try:
        compile(text, str(TARGET), "exec")
    except Exception as exc:
        print(f"[ERROR] Syntax check failed: {exc}")
        TARGET.write_text(original, encoding="utf-8", newline="\n")
        print("[OK] Original file restored after failed patch.")
        return 1

    print(f"[OK] Patch applied successfully: {TARGET}")
    print("[OK] Python syntax check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())