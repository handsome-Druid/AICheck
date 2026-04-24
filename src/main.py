import argparse
import asyncio
import subprocess
import sys
from typing import Protocol, cast

try:
    from src.controllers.vllm_test_controller import run
except ImportError:
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
    from src.controllers.vllm_test_controller import run


class QApplicationInstance(Protocol):
    def exec(self) -> int: ...


class QApplicationFactory(Protocol):
    def __call__(self, *args: object, **kwargs: object) -> QApplicationInstance: ...


class MainWindowInstance(Protocol):
    controller: object | None

    def show(self) -> None: ...


class MainWindowFactory(Protocol):
    def __call__(self, *args: object, **kwargs: object) -> MainWindowInstance: ...


class MainControllerFactory(Protocol):
    def __call__(self, *args: object, **kwargs: object) -> object: ...


QApplication: QApplicationFactory | None = None
MainController: MainControllerFactory | None = None
MainWindow: MainWindowFactory | None = None


def _load_gui_components() -> tuple[QApplicationFactory, MainControllerFactory, MainWindowFactory]:
    global QApplication, MainController, MainWindow

    if QApplication is None or MainController is None or MainWindow is None:
        try:
            from PySide6.QtWidgets import QApplication as _QApplication
            from src.controllers.main_controller import MainController as _MainController
            from src.views.main_view import MainWindow as _MainWindow
        except ImportError:
            import os

            sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
            from PySide6.QtWidgets import QApplication as _QApplication
            from src.controllers.main_controller import MainController as _MainController
            from src.views.main_view import MainWindow as _MainWindow

        QApplication = cast(QApplicationFactory, _QApplication)
        MainController = cast(MainControllerFactory, _MainController)
        MainWindow = cast(MainWindowFactory, _MainWindow)

    assert QApplication is not None
    assert MainController is not None
    assert MainWindow is not None
    return QApplication, MainController, MainWindow


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nogui", action="store_true", help="Run without the Qt GUI")
    parser.add_argument("--nopause", action="store_true", help="Do not pause the console after finishing")
    args = parser.parse_args()

    if args.nogui:
        asyncio.run(run())
        if not args.nopause:
            subprocess.run("pause", shell=True)
        return

    qapplication_class, main_controller_class, main_window_class = _load_gui_components()
    app = qapplication_class(sys.argv)
    window = main_window_class()
    controller = main_controller_class(window)
    window.controller = controller
    window.show()
    app.exec()


if __name__ == "__main__":
    main()