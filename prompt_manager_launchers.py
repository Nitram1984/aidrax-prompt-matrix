#!/usr/bin/env python3

import sys

from main import cmd_manus_open


def manus_web_main() -> None:
    task_id = sys.argv[1] if len(sys.argv) > 1 else None
    cmd_manus_open(task_id=task_id)
