import logging
from pathlib import Path

from core.logging_setup import configure_logging, shutdown_logging


def test_logging_reconfigures_owned_handlers_and_writes_to_new_directory(tmp_path: Path) -> None:
    logger = logging.getLogger("myassistant")
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()

    try:
        configure_logging(first_dir, "DEBUG")
        configure_logging(second_dir, "WARNING")
        assert logger.level == logging.WARNING
        assert len([handler for handler in logger.handlers if getattr(handler, "_myassistant_owned", False)]) == 2

        logger.warning("second-directory-marker")
        for handler in logger.handlers:
            handler.flush()

        assert "second-directory-marker" in (second_dir / "myassistant.log").read_text(encoding="utf-8")
        assert "second-directory-marker" not in (first_dir / "myassistant.log").read_text(encoding="utf-8")
    finally:
        shutdown_logging(logger)
