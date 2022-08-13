import dataclasses
from datetime import datetime
from enum import Enum, IntEnum, auto
import pandas as pd
import sys


class Severity(IntEnum):
    Critical = auto()
    Error = auto()
    Warn = auto()
    Note = auto()
    Debug = auto()
    Trace = auto()


SEVERITY_MAP = {s.name.lower(): s for s in Severity}


@dataclasses.dataclass
class LogMsg:
    time: float = None
    step: int = None
    severity: Severity = None
    host: str = None
    app: str = None
    source: str = None
    msg: str = None


def decode_text_log(text_log):
    fmt = '%Y-%m-%dT%H:%M:%S.%f'

    msgs = []

    with open(text_log, 'r') as fn:
        log_line = ''
        for line in fn.readlines():
            # Handle multi-line log lines (ensure the log ends appropriately)
            log_line += line
            if log_line[-2:] != "]\n":
                continue
            msg_prts = log_line.strip().lstrip('[').rstrip(']').split(']|[')
            # After processing, clear the line.
            log_line = ''
            dt = datetime.strptime('T'.join(msg_prts[:2]), fmt)

            if len(msg_prts) < 7:
                continue

            _, _, step, severity, host_app, source, msg = msg_prts

            lm = LogMsg(dt.timestamp(), int(step), SEVERITY_MAP[severity.strip().lower()],
                        *(host_app.split(':')), source, msg)

            msgs.append(lm)

    return msgs
