#!/usr/bin/env python3
from __future__ import annotations

from scraper import set_trace as set_scr_trace, get_driver, open_and_prepare_resilient

class DriverManager:
    def __init__(self, debug: bool=False, trace: bool=False, artifacts_dir: str="./artifacts"):
        self.debug = debug
        self.trace = trace
        self.artifacts_dir = artifacts_dir
        self.d = None
        set_scr_trace(trace, artifacts_dir)

    def ensure(self):
        if self.d: return self.d
        self.d = get_driver(debug=self.debug)
        if not self.d:
            raise RuntimeError("Failed to start Chrome driver")
        return self.d

    def reset(self):
        try:
            if self.d: self.d.quit()
        except Exception:
            pass
        self.d = None

    def open(self, url: str):
        d = self.ensure()
        return open_and_prepare_resilient(d, url, debug=self.debug)


