#!/usr/bin/env python3
"""SMDATA Fixer: GUI for repairing SMART Mobile 1.0.612 JSON exports.

Wraps ``fix_smdata_612.fix_file`` in a small Tkinter window so field staff can
pick several SMDATA_*.json files, choose an output folder and repair them
without using the command line. Built into a single Windows .exe with
PyInstaller (see build_exe.sh).
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from fix_smdata_612 import FixResult, fix_file

APP_TITLE = "SMDATA Fixer – Perbaikan data SMART Mobile 1.0.612"


class FixerApp(tk.Tk):
    """Main window: file list, output folder, run button and log."""

    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("780x560")
        self.minsize(640, 460)

        self.files: list[Path] = []
        self.output_dir = tk.StringVar()
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker: threading.Thread | None = None

        self._build_ui()
        self.after(100, self._drain_events)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        files_frame = ttk.LabelFrame(self, text="1. File JSON dari SMART Mobile (SMDATA_*.json)")
        files_frame.pack(fill="both", expand=True, **pad)

        list_frame = ttk.Frame(files_frame)
        list_frame.pack(fill="both", expand=True, padx=6, pady=4)
        self.file_list = tk.Listbox(list_frame, selectmode="extended", height=7)
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_list.yview)
        self.file_list.configure(yscrollcommand=scroll.set)
        self.file_list.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        buttons = ttk.Frame(files_frame)
        buttons.pack(fill="x", padx=6, pady=(0, 6))
        self.add_btn = ttk.Button(buttons, text="Tambah file…", command=self.add_files)
        self.add_btn.pack(side="left")
        self.remove_btn = ttk.Button(buttons, text="Hapus terpilih", command=self.remove_selected)
        self.remove_btn.pack(side="left", padx=6)
        self.clear_btn = ttk.Button(buttons, text="Bersihkan", command=self.clear_files)
        self.clear_btn.pack(side="left")
        self.count_label = ttk.Label(buttons, text="0 file")
        self.count_label.pack(side="right")

        out_frame = ttk.LabelFrame(self, text="2. Folder output")
        out_frame.pack(fill="x", **pad)
        ttk.Entry(out_frame, textvariable=self.output_dir).pack(side="left", fill="x", expand=True, padx=6, pady=6)
        self.browse_btn = ttk.Button(out_frame, text="Pilih…", command=self.choose_output)
        self.browse_btn.pack(side="left", padx=(0, 6))

        run_frame = ttk.Frame(self)
        run_frame.pack(fill="x", **pad)
        self.run_btn = ttk.Button(run_frame, text="3. Perbaiki", command=self.start)
        self.run_btn.pack(side="left")
        self.open_btn = ttk.Button(run_frame, text="Buka folder output", command=self.open_output, state="disabled")
        self.open_btn.pack(side="left", padx=6)
        self.progress = ttk.Progressbar(run_frame, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=(6, 0))

        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log = tk.Text(log_frame, height=10, state="disabled", wrap="word")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=log_scroll.set)
        self.log.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        log_scroll.pack(side="right", fill="y", pady=6)
        self.log.tag_configure("ok", foreground="#1a7f37")
        self.log.tag_configure("warn", foreground="#9a6700")
        self.log.tag_configure("err", foreground="#cf222e")

    # ------------------------------------------------------------- actions
    def add_files(self) -> None:
        chosen = filedialog.askopenfilenames(
            title="Pilih file SMDATA",
            filetypes=[("SMART Mobile JSON", "*.json"), ("Semua file", "*.*")],
        )
        for name in chosen:
            path = Path(name)
            if path not in self.files:
                self.files.append(path)
                self.file_list.insert("end", str(path))
        if self.files and not self.output_dir.get():
            self.output_dir.set(str(self.files[0].parent / "fixed"))
        self._update_count()

    def remove_selected(self) -> None:
        for index in reversed(self.file_list.curselection()):
            self.file_list.delete(index)
            del self.files[index]
        self._update_count()

    def clear_files(self) -> None:
        self.file_list.delete(0, "end")
        self.files.clear()
        self._update_count()

    def choose_output(self) -> None:
        folder = filedialog.askdirectory(title="Pilih folder output", initialdir=self.output_dir.get() or None)
        if folder:
            self.output_dir.set(folder)

    def open_output(self) -> None:
        folder = self.output_dir.get()
        if not folder or not Path(folder).is_dir():
            return
        if sys.platform == "win32":
            os.startfile(folder)  # noqa: S606 - opens Explorer on the chosen folder
        else:
            subprocess.Popen(["xdg-open", folder])

    def start(self) -> None:
        if not self.files:
            messagebox.showwarning(APP_TITLE, "Belum ada file yang dipilih.")
            return
        if not self.output_dir.get().strip():
            messagebox.showwarning(APP_TITLE, "Pilih folder output terlebih dahulu.")
            return

        out_dir = Path(self.output_dir.get().strip()).resolve()
        if any(src.resolve().parent == out_dir for src in self.files):
            messagebox.showerror(
                APP_TITLE,
                "Folder output tidak boleh sama dengan folder file asli,\n"
                "agar file asli tidak tertimpa. Pilih folder lain.",
            )
            return

        existing = [src.name for src in self.files if (out_dir / src.name).exists()]
        if existing and not messagebox.askyesno(
            APP_TITLE,
            f"{len(existing)} file sudah ada di folder output dan akan ditimpa:\n\n"
            + "\n".join(existing[:10])
            + ("\n…" if len(existing) > 10 else "")
            + "\n\nLanjutkan?",
        ):
            return

        self._set_busy(True)
        self.progress.configure(maximum=len(self.files), value=0)
        self._log(f"Memproses {len(self.files)} file → {out_dir}\n")
        self.worker = threading.Thread(target=self._work, args=(list(self.files), out_dir), daemon=True)
        self.worker.start()

    # -------------------------------------------------------------- worker
    def _work(self, files: list[Path], out_dir: Path) -> None:
        """Runs off the UI thread; reports back through ``self.events``."""
        for src in files:
            self.events.put(("start", src))
            try:
                self.events.put(("done", fix_file(src, out_dir)))
            except Exception as exc:  # report every failure, keep going
                self.events.put(("fail", (src, exc)))
        self.events.put(("finished", None))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                self._handle_event(kind, payload)
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _handle_event(self, kind: str, payload: object) -> None:
        if kind == "start":
            self._log(f"• {payload.name} … ")
        elif kind == "done":
            self._log_result(payload)
            self.progress.step(1)
        elif kind == "fail":
            src, exc = payload
            self._log(f"GAGAL\n    {exc}\n", "err")
            self._failed += 1
            self.progress.step(1)
        elif kind == "finished":
            self._set_busy(False)
            self.open_btn.configure(state="normal")
            summary = (
                f"Selesai.\n\nBerhasil: {self._ok}\nDengan peringatan: {self._warned}\nGagal: {self._failed}\n\n"
                f"Hasil ada di:\n{self.output_dir.get()}"
            )
            self._log("\n" + summary.replace("\n\n", "\n") + "\n")
            (messagebox.showwarning if self._failed or self._warned else messagebox.showinfo)(APP_TITLE, summary)

    def _log_result(self, result: FixResult) -> None:
        total = sum(result.removed.values())
        versions = ", ".join(sorted(result.versions)) or "-"
        if result.problems:
            self._warned += 1
            self._log("OK dengan peringatan\n", "warn")
        else:
            self._ok += 1
            self._log("OK\n", "ok")
        self._log(
            f"    versi {versions} · {result.sightings} observasi · {result.features} feature · "
            f"{total} nilai kosong dibuang\n"
        )
        if not total:
            self._log("    (file ini sudah normal, tidak ada yang diubah)\n")
        for problem in result.problems:
            self._log(f"    PERINGATAN: {problem} – SMART Desktop bisa berhenti di titik ini\n", "warn")

    # ------------------------------------------------------------- helpers
    def _set_busy(self, busy: bool) -> None:
        if busy:
            self._ok = self._warned = self._failed = 0
        state = "disabled" if busy else "normal"
        for widget in (self.add_btn, self.remove_btn, self.clear_btn, self.browse_btn, self.run_btn):
            widget.configure(state=state)

    def _update_count(self) -> None:
        self.count_label.configure(text=f"{len(self.files)} file")

    def _log(self, text: str, tag: str | None = None) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text, (tag,) if tag else ())
        self.log.see("end")
        self.log.configure(state="disabled")


def main() -> None:
    FixerApp().mainloop()


if __name__ == "__main__":
    main()
