"""Desktop application entry point."""

import sys
from pathlib import Path
from typing import Optional, Sequence

from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QMessageBox

from ...core import setup_logging
from ...core.config import PROJECT_NAME, PROJECT_VERSION
from ...core.container import get_container
from ...core.container.registration import register_all_services
from ...core.validation import validate_and_raise
from .controller import OdysseusController


def build_engine(controller: OdysseusController) -> QQmlApplicationEngine:
    """Create and load the QML engine for a controller."""
    engine = QQmlApplicationEngine()
    if controller.parent() is None:
        controller.setParent(engine)
    engine.rootContext().setContextProperty("odysseus", controller)
    qml_path = Path(__file__).with_name("qml") / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    return engine


def main(args: Optional[Sequence[str]] = None) -> int:
    """Launch the native Odysseus desktop application."""
    setup_logging()
    QCoreApplication.setOrganizationName("Odysseus")
    QCoreApplication.setApplicationName(PROJECT_NAME)
    QCoreApplication.setApplicationVersion(PROJECT_VERSION)
    QQuickStyle.setStyle("Fusion")
    application = QApplication(list(args) if args is not None else sys.argv)

    try:
        validate_and_raise()
        container = get_container()
        register_all_services(container)
        controller = OdysseusController(
            container.get("recording_workflow"),
            container.get("release_workflow"),
            settings_service=container.get("api_settings_service"),
        )
        engine = build_engine(controller)
        if not engine.rootObjects():
            raise RuntimeError("The desktop interface could not be loaded")
    except Exception as error:
        QMessageBox.critical(None, "Odysseus could not start", str(error))
        return 1

    # Keep Python-owned Qt objects alive for the complete event loop.
    application._odysseus_controller = controller
    application._odysseus_engine = engine
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
