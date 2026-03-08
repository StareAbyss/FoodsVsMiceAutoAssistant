class SimpleLogger:
    """简单日志记录器"""

    def __init__(self, callback,enable=False):
        self.callback = callback
        self.enable=enable

    def _log(self, level: str, message: str):
        log_text = f"[{level}]: {message}"
        if self.enable:
            print(log_text)
        if self.callback:
            self.callback(level,message)

    def info(self, message: str):
        self._log("INFO", message)

    def warning(self, message: str):
        self._log("WARNING", message)

    def error(self, message: str):
        self._log("ERROR", message)
