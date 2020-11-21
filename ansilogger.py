from threading import Thread


class AnsiLogger(Thread):

    NORMAL = "\033[0m"

    status_color = {
        "error": "\033[91m",
        "processing": "\033[31m",
        "processed": "\033[33m",
        "finished": "\033[32m"
    }

    def __init__(self, parent_connection, use_ansi=True):
        super().__init__()
        self.parent_connection = parent_connection
        if use_ansi:
            self.question_rows = dict()
            self.current_row = 0
            self.log = self.ansi_log
        else:
            self.log = self.non_ansi_log

    def ansi_log(self, name, status):
        line = f"[{AnsiLogger.status_color[status]}{status:>10}{AnsiLogger.NORMAL}] {name}"
        if name in self.question_rows:
            print("\0337", end="")
            self.up(self.current_row - self.question_rows[name])
            print(f"{line}\0338", end="", flush=True)
        else:
            self.question_rows[name] = self.current_row
            self.current_row += 1
            print(line, flush=True)

    def run(self):
        try:
            while True:
                status, name = self.parent_connection.recv()
                if status == "completed":
                    break
                else:
                    self.log(name, status)
        except EOFError:
            pass

    def non_ansi_log(self, name, status):
        print(f"[{status}] {name}")

    @staticmethod
    def up(lines):
        print(f"\033[{lines}F", end="")
