"""Smoke tests: every dashboard page runs without an exception, and the filters change what is shown.
Uses dashboard/data (committed), so no raw data are needed."""
import sys
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

DASH = Path(__file__).resolve().parents[1] / "dashboard"
sys.path.insert(0, str(DASH))
PAGES = ["views/overview.py", "views/priority.py", "views/allocation.py",
         "views/patterns.py", "views/evaluation.py", "views/about.py"]


def run(page=None):
    at = AppTest.from_file(str(DASH / "app.py"), default_timeout=120)
    at.run()
    if page and page != "views/overview.py":
        at.switch_page(page).run()
    return at


@pytest.mark.parametrize("page", PAGES)
def test_page_runs_without_exception(page):
    at = run(page)
    assert not at.exception, [e.value for e in at.exception]


def test_city_filter_changes_the_selection():
    at = run()
    ctx_all = len(at.session_state["ctx"]["view"])
    at.selectbox(key="place_sel").select("Manchester").run()
    assert not at.exception
    n_city = len(at.session_state["ctx"]["view"])
    assert 0 < n_city < ctx_all


def test_weights_change_the_score():
    at = run()
    before = at.session_state["ctx"]["view"]["gap"].mean()
    at.sidebar.slider(key="w_access").set_value(100).run()
    after = at.session_state["ctx"]["view"]["gap"].mean()
    assert not at.exception and before != after
