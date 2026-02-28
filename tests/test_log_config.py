"""
Tests for LogConfig: configure, get_logger, set_level, silence.
"""

import logging
import os
import tempfile
import pytest
from instaapi.log_config import LogConfig


class TestLogConfig:
    """Test centralized logging configuration."""

    def test_configure_default(self):
        logger = LogConfig.configure(level="DEBUG")
        assert logger.name == "instaapi"
        assert logger.level == logging.DEBUG
        assert LogConfig.is_configured() is True

    def test_configure_level(self):
        logger = LogConfig.configure(level="ERROR")
        assert logger.level == logging.ERROR

    def test_console_handler(self):
        logger = LogConfig.configure(level="INFO", console=True)
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "StreamHandler" in handler_types

    def test_no_console_handler(self):
        logger = LogConfig.configure(level="INFO", console=False)
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "StreamHandler" not in handler_types

    def test_file_handler(self):
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            path = f.name
        try:
            logger = LogConfig.configure(level="DEBUG", filename=path, console=False)
            handler_types = [type(h).__name__ for h in logger.handlers]
            assert "RotatingFileHandler" in handler_types
        finally:
            # Clean up
            for h in logger.handlers[:]:
                h.close()
                logger.removeHandler(h)
            os.unlink(path)

    def test_get_logger(self):
        child = LogConfig.get_logger("client")
        assert child.name == "instaapi.client"

    def test_get_logger_already_namespaced(self):
        child = LogConfig.get_logger("instaapi.batch")
        assert child.name == "instaapi.batch"

    def test_set_level(self):
        LogConfig.configure(level="INFO")
        LogConfig.set_level("DEBUG")
        root = logging.getLogger("instaapi")
        assert root.level == logging.DEBUG

    def test_silence(self):
        LogConfig.configure(level="DEBUG")
        LogConfig.silence()
        root = logging.getLogger("instaapi")
        assert root.level > logging.CRITICAL

    def test_child_logger_inherits(self):
        LogConfig.configure(level="DEBUG", console=False)
        parent = logging.getLogger("instaapi")
        child = logging.getLogger("instaapi.client")
        assert child.getEffectiveLevel() == logging.DEBUG
