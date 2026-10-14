"""Optional PySide6 desktop interface. Importing app.ui does not load Qt."""

from pathlib import Path


def launch_gui(
    *,
    data_dir: Path,
    demo: bool = False,
    network_probe: bool = False,
    backend_name: str = "mock",
) -> int:
    """Start the desktop app; each repair still requires action-level consent."""
    import sys

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.service import GuardianService
    from app.ui.main_window import MainWindow

    application = QApplication.instance() or QApplication(sys.argv[:1])
    application.setApplicationName("PC Guardian AI")
    service = GuardianService(
        data_dir=Path(data_dir),
        demo=demo,
        network_probe=network_probe,
        backend_name=backend_name,
    )
    window = MainWindow(service, demo=demo, network_probe=network_probe)
    window.show()
    QTimer.singleShot(0, window.scan)
    return application.exec()


__all__ = ["launch_gui"]
