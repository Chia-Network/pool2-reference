from __future__ import annotations

import gzip
import logging
import logging.handlers
import pathlib
import shutil

from api.server import LoggingConfig


def gzip_rotator(source: str, dest: str) -> None:
    with pathlib.Path(source).open("rb") as f_in, gzip.open(f"{dest}.gz", "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    pathlib.Path(source).unlink()


def gzip_namer(name: str) -> str:
    return name + ".gz"


def setup_logging(root: logging.Logger, log_config: LoggingConfig) -> None:
    level = getattr(logging, log_config["log_level"])
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    root.setLevel(level)
    root.handlers.clear()

    if log_config["log_stdout"]:
        stdout_handler = logging.StreamHandler()
        stdout_handler.setLevel(level)
        stdout_handler.setFormatter(formatter)
        root.addHandler(stdout_handler)

    if log_config["log_filename"]:
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_config["log_filename"],
            maxBytes=int(log_config["log_max_bytes_rotation"]),
            backupCount=int(log_config["log_maxfilesrotation"]),
        )
        if log_config["log_use_gzip"]:
            file_handler.rotator = gzip_rotator
            file_handler.namer = gzip_namer
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    if log_config["log_syslog"]:
        syslog_handler = logging.handlers.SysLogHandler(
            address=(log_config["log_syslog_host"], int(log_config["log_syslog_port"])),
        )
        syslog_handler.setLevel(level)
        syslog_handler.setFormatter(formatter)
        root.addHandler(syslog_handler)
