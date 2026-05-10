import sys
import os
import time
import threading
from datetime import datetime

class Logger:
    def __init__(self):
        self.sink = sys.stderr
        self.log_format = "{time} | {level} | {message}"
        self.encoding = "utf-8"
        self.level = "DEBUG"
        self.rotation = None
        self.retention = None
        self.diagnose = True
        self.enqueue = False

        self.file = None
        self.lock = threading.Lock()
        self.current_size = 0

    def add(
        self,
        sink,
        format="{time} | {level} | {message}",
        encoding="utf-8",
        level="DEBUG",
        rotation=None,
        retention=None,
        diagnose=True,
        enqueue=False
    ):
        with self.lock:
            self.sink = sink
            self.log_format = format
            self.encoding = encoding
            self.level = level.upper()
            self.rotation = rotation
            self.retention = retention
            self.diagnose = diagnose
            self.enqueue = enqueue

            # 打开文件（真正生效）
            if isinstance(sink, str):
                self.file = open(sink, "a", encoding=encoding)

    def remove(self):
        with self.lock:
            if self.file:
                self.file.close()
                self.file = None

    def _should_rotate(self):
        # rotation 真正生效：按大小切割
        if not self.rotation or not self.file:
            return False
        try:
            if str(self.rotation).endswith("MB"):
                mb = float(self.rotation.replace("MB", ""))
                limit = mb * 1024 * 1024
                return self.file.tell() >= limit
        except:
            pass
        return False

    def _rotate(self):
        # 真正执行日志切割
        if self.file:
            self.file.close()
            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = f"{self.sink}.{now}"
            os.rename(self.sink, new_name)
            self.file = open(self.sink, "a", encoding=self.encoding)

    def _format_msg(self, level, message):
        # format 格式真正生效
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return self.log_format \
            .replace("{time}", time_str) \
            .replace("{level}", level) \
            .replace("{message}", message)

    def log(self, level: str, message: str = ""):
        level = level.upper()
        with self.lock:
            if self._should_rotate():
                self._rotate()

            msg = self._format_msg(level, message)
            print(msg)

            if self.file:
                self.file.write(msg + "\n")
                self.file.flush()

    def trace(self, msg): self.log("TRACE", msg)
    def debug(self, msg): self.log("DEBUG", msg)
    def info(self, msg):  self.log("INFO", msg)
    def success(self, msg): self.log("SUCCESS", msg)
    def warning(self, msg): self.log("WARNING", msg)
    def error(self, msg): self.log("ERROR", msg)
    def critical(self, msg): self.log("CRITICAL", msg)

logger = Logger()