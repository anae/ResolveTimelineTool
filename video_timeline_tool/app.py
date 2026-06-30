from __future__ import annotations

import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Tuple

from .engine import process_timeline


class TimelineApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Resolve Timeline Tool")
        self.geometry("720x430")
        self.minsize(640, 390)

        self._queue: "queue.Queue[Tuple[str, Any]]" = queue.Queue()
        self._worker: threading.Thread | None = None

        self.source_var = tk.StringVar()
        self.style_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.max_segment_var = tk.DoubleVar(value=6.0)
        self.status_var = tk.StringVar(value="Pret")
        self.progress_var = tk.DoubleVar(value=0.0)

        self._build_ui()
        self.after(100, self._poll_queue)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(1, weight=1)

        ttk.Label(root, text="Dossier source").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(root, textvariable=self.source_var).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(root, text="Parcourir", command=self._pick_source).grid(row=0, column=2, sticky="ew")

        ttk.Label(root, text="Style .md").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(root, textvariable=self.style_var).grid(row=1, column=1, sticky="ew", padx=8)
        style_buttons = ttk.Frame(root)
        style_buttons.grid(row=1, column=2, sticky="ew")
        ttk.Button(style_buttons, text="Parcourir", command=self._pick_style).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(style_buttons, text="Ouvrir", command=self._open_style).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(root, text="Sortie").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(root, textvariable=self.output_var).grid(row=2, column=1, sticky="ew", padx=8)
        ttk.Button(root, text="Parcourir", command=self._pick_output).grid(row=2, column=2, sticky="ew")

        ttk.Label(root, text="Duree max segment").grid(row=3, column=0, sticky="w", pady=4)
        segment_frame = ttk.Frame(root)
        segment_frame.grid(row=3, column=1, sticky="w", padx=8)
        ttk.Spinbox(
            segment_frame,
            from_=1.0,
            to=120.0,
            increment=0.5,
            textvariable=self.max_segment_var,
            width=8,
        ).pack(side=tk.LEFT)
        ttk.Label(segment_frame, text="secondes").pack(side=tk.LEFT, padx=(8, 0))

        action_frame = ttk.Frame(root)
        action_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(18, 10))
        action_frame.columnconfigure(0, weight=1)
        action_frame.columnconfigure(1, weight=1)
        self.generate_button = ttk.Button(action_frame, text="Generer timeline", command=self._start_processing)
        self.generate_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.rerun_button = ttk.Button(action_frame, text="Relancer apres modification .md", command=self._start_processing)
        self.rerun_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        ttk.Progressbar(root, variable=self.progress_var, maximum=100).grid(
            row=5, column=0, columnspan=3, sticky="ew", pady=(4, 2)
        )
        ttk.Label(root, textvariable=self.status_var).grid(row=6, column=0, columnspan=3, sticky="w")

        self.log = tk.Text(root, height=10, wrap="word")
        self.log.grid(row=7, column=0, columnspan=3, sticky="nsew", pady=(10, 0))
        root.rowconfigure(7, weight=1)
        self.log.insert("end", "Les exports EDL et FCPXML seront crees dans le dossier de sortie.\n")
        self.log.configure(state="disabled")

    def _pick_source(self) -> None:
        directory = filedialog.askdirectory(title="Choisir le dossier de rushs")
        if directory:
            self.source_var.set(directory)
            if not self.output_var.get():
                self.output_var.set(str(Path(directory) / "_resolve_timeline_exports"))

    def _pick_style(self) -> None:
        filename = filedialog.askopenfilename(
            title="Choisir le fichier style Markdown",
            filetypes=(("Markdown", "*.md"), ("Tous les fichiers", "*.*")),
        )
        if filename:
            self.style_var.set(filename)

    def _pick_output(self) -> None:
        directory = filedialog.askdirectory(title="Choisir le dossier de sortie")
        if directory:
            self.output_var.set(directory)

    def _open_style(self) -> None:
        path = self.style_var.get().strip()
        if not path:
            return
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", path], check=False)
            elif sys.platform.startswith("win"):
                subprocess.run(["cmd", "/c", "start", "", path], check=False)
            else:
                subprocess.run(["xdg-open", path], check=False)
        except OSError as exc:
            messagebox.showerror("Ouverture impossible", str(exc))

    def _start_processing(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        try:
            source_dir = Path(self.source_var.get().strip())
            style_path = Path(self.style_var.get().strip())
            output_dir = Path(self.output_var.get().strip()) if self.output_var.get().strip() else None
            max_segment = float(self.max_segment_var.get())
        except ValueError:
            messagebox.showerror("Parametre invalide", "La duree maximale doit etre un nombre.")
            return

        if not source_dir.is_dir():
            messagebox.showerror("Dossier invalide", "Choisis un dossier source valide.")
            return
        if not style_path.is_file() or style_path.suffix.lower() != ".md":
            messagebox.showerror("Style invalide", "Choisis un fichier .md valide.")
            return

        self._set_running(True)
        self._append_log("Traitement lance. Le style Markdown est relu depuis disque.\n")
        self._worker = threading.Thread(
            target=self._run_worker,
            args=(source_dir, style_path, output_dir, max_segment),
            daemon=True,
        )
        self._worker.start()

    def _run_worker(
        self,
        source_dir: Path,
        style_path: Path,
        output_dir: Path | None,
        max_segment: float,
    ) -> None:
        try:
            result = process_timeline(
                source_dir=source_dir,
                style_path=style_path,
                max_segment_seconds=max_segment,
                output_dir=output_dir,
                progress=lambda fraction, message: self._queue.put(("progress", (fraction, message))),
            )
            self._queue.put(("done", result))
        except Exception as exc:
            self._queue.put(("error", exc))

    def _poll_queue(self) -> None:
        while True:
            try:
                event, payload = self._queue.get_nowait()
            except queue.Empty:
                break

            if event == "progress":
                fraction, message = payload
                self.progress_var.set(fraction * 100)
                self.status_var.set(message)
            elif event == "done":
                self._set_running(False)
                self.progress_var.set(100)
                self.status_var.set("Termine")
                self._append_log(
                    "Exports crees:\n"
                    f"- EDL: {payload.edl_path}\n"
                    f"- FCPXML: {payload.fcpxml_path}\n"
                    f"- Rapport: {payload.report_path}\n"
                )
            elif event == "error":
                self._set_running(False)
                self.status_var.set("Erreur")
                self._append_log(f"Erreur: {payload}\n")
                messagebox.showerror("Traitement impossible", str(payload))

        self.after(100, self._poll_queue)

    def _set_running(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        self.generate_button.configure(state=state)
        self.rerun_button.configure(state=state)
        if running:
            self.progress_var.set(0)
            self.status_var.set("Demarrage")

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")


def main() -> None:
    app = TimelineApp()
    app.mainloop()
