import os
import sys
from ctypes.util import find_library


def _should_use_qt_backend():
    if os.environ.get("BIORANK_DISABLE_QT") == "1":
        return False
    if os.environ.get("BIORANK_FORCE_QT") == "1":
        return True
    if sys.platform.startswith("win"):
        return True

    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        if find_library("xcb-cursor") or find_library("xcb-cursor0"):
            return True

    return False


def run_optimizer_app(selected_disease="BRCA"):
    if _should_use_qt_backend():
        from PySide6.QtWidgets import QApplication

        from biorank_qt import theme
        from biorank_qt.optimizer_window import BioRankOptimizerWindow

        app = QApplication.instance() or QApplication(sys.argv)
        app.setStyleSheet(theme.app_stylesheet())
        window = BioRankOptimizerWindow(selected_disease=selected_disease)
        window.show()
        return app.exec()

    import tkinter as tk

    from biorank_ui.optuna_compare_window import AlphaBetaCompareOptimizationWindow

    root = tk.Tk()
    root.withdraw()
    AlphaBetaCompareOptimizationWindow(parent=root, selected_disease=selected_disease)
    root.mainloop()
    return 0
