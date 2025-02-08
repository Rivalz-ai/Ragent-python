import logging
import os
import sys

class RomeLogger(logging.Logger):
    ANSI_COLORS = {
        "black": "\x1b[30m",
        "red": "\x1b[31m",
        "green": "\x1b[32m",
        "yellow": "\x1b[33m",
        "blue": "\x1b[34m",
        "magenta": "\x1b[35m",
        "cyan": "\x1b[36m",
        "white": "\x1b[37m",
        "reset": "\x1b[0m",
    }

    def __init__(self, name="RomeLogger", verbose=False, use_icons=True):
        super().__init__(name)
        self.verbose = verbose
        self.use_icons = use_icons
        self.close_by_newline = True
        self._stream_handler = logging.StreamHandler(sys.stdout)
        self._stream_handler.setFormatter(logging.Formatter("%(message)s"))
        self.addHandler(self._stream_handler)
        self.setLevel(logging.DEBUG if verbose else logging.INFO)

        self.logsTitle = "LOGS"
        self.warningsTitle = "WARNINGS"
        self.errorsTitle = "ERRORS"
        self.informationsTitle = "INFORMATIONS"
        self.successesTitle = "SUCCESS"
        self.debugsTitle = "DEBUG"
        self.assertsTitle = "ASSERT"

        self.debug(f"[Init] verbose={verbose}, use_icons={use_icons}")

    def _colorize(self, text, fg="white"):
        color_code = self.ANSI_COLORS.get(fg.lower(), self.ANSI_COLORS["white"])
        reset_code = self.ANSI_COLORS["reset"]
        return f"{color_code}{text}{reset_code}"

    def clear(self):
        if os.name == "posix":
            os.system("clear")
        elif os.name == "nt":
            os.system("cls")

    def _log_group(self, level, message_list, fg, icon, title):
        if len(message_list) > 1:
            self.log(level, self._colorize((icon + " " if self.use_icons else "") + title, fg))
            for msg in message_list:
                self.log(level, self._colorize(f"  {msg}", fg))
            if self.close_by_newline:
                self.log(level, "")
        else:
            prefix = icon + " " if self.use_icons else ""
            for msg in message_list:
                self.log(level, self._colorize(prefix + str(msg), fg))
            if self.close_by_newline:
                self.log(level, "")

    def custom_log(self, *messages):
        self._log_group(logging.INFO, messages, "white", "○", self.logsTitle)

    def warn_log(self, *messages):
        self._log_group(logging.WARNING, messages, "yellow", "⚠", self.warningsTitle)

    def error_log(self, *messages):
        self._log_group(logging.ERROR, messages, "red", "⛔", self.errorsTitle)

    def info_log(self, *messages):
        self._log_group(logging.INFO, messages, "blue", "ℹ", self.informationsTitle)

    def debug_log(self, *messages):
        if self.verbose:
            self._log_group(logging.DEBUG, messages, "magenta", "⁛", self.debugsTitle)

    def success_log(self, *messages):
        self._log_group(logging.INFO, messages, "green", "✓", self.successesTitle)

    def assert_log(self, *messages):
        self._log_group(logging.INFO, messages, "cyan", "!", self.assertsTitle)

    def progress(self, message: str):
        if sys.stdout.isatty():
            sys.stdout.write("\r" + message)
            sys.stdout.flush()
        else:
            self.info_log(message)

# Example usage:
rome_logger = RomeLogger(verbose=True, use_icons=True)
# logger.clear()
# logger.custom_log("Hello from custom log.")
# logger.warn_log("This is a warning.")
# logger.error_log("This is an error.")
# logger.info_log("Just an info.")
# logger.debug_log("Detailed debug here.")
# logger.success_log("We did it!")
# logger.progress("Loading...")