"""
conftest.py — pytest fixtures for ShopMate-R tests.

The production `pepper_api` opens an SSH session at import time, and
`temi_api` POSTs to Temi's HTTP endpoint on every call. Our tests
can't rely on either being reachable, so we patch both before any
test module imports them.

This mirrors the same trick `tablet_preview.py` uses in production —
inject a no-op stub into `sys.modules` under the name the real module
would be imported as.
"""

from __future__ import annotations
import sys
import types

import pytest


# -------------------------------------------------------------------------
# Stub out pypepper_ssh BEFORE pepper_api imports it.
# -------------------------------------------------------------------------

class _FakePepper:
    """No-op stand-in for PepperRobotSSH. Records calls so tests can
    assert on them if needed."""

    def __init__(self, *a, **kw):
        self.calls: list[tuple] = []

    def _rec(self, name, *args, **kw):
        self.calls.append((name, args, kw))

    def say(self, *a, **kw):               self._rec("say", *a, **kw)
    def set_system_volume(self, *a, **kw): self._rec("set_volume", *a, **kw)
    def play_animation(self, *a, **kw):    self._rec("animation", *a, **kw)
    def show_image(self, *a, **kw):        self._rec("show_image", *a, **kw)
    def show_html(self, *a, **kw):         self._rec("show_html", *a, **kw)
    def clear_tablet(self, *a, **kw):      self._rec("clear", *a, **kw)
    def record_audio(self, *a, **kw):      self._rec("record", *a, **kw)
    def close(self, *a, **kw):             self._rec("close", *a, **kw)


_stub = types.ModuleType("pypepper_ssh")
_stub.PepperRobotSSH = _FakePepper
sys.modules["pypepper_ssh"] = _stub


# -------------------------------------------------------------------------
# Stub requests.post so temi_api can't actually try to reach Temi.
# -------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Every test gets requests.post stubbed to a 200/ok response.
    Prevents accidental hits to the dashboard or Temi during testing."""
    import requests

    class _FakeResp:
        status_code = 200
        def json(self):   return {"ok": True}
        @property
        def text(self):   return "ok"

    def _fake_post(*a, **kw):
        return _FakeResp()

    def _fake_get(*a, **kw):
        return _FakeResp()

    monkeypatch.setattr(requests, "post", _fake_post)
    monkeypatch.setattr(requests, "get",  _fake_get)
