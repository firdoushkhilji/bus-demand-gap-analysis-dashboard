"""Tests the GTFS functions in notebook 04 on a tiny synthetic feed (weekday, Saturday, Sunday).
The notebook's function cells are executed directly, so the code under test is the code that runs on the real feed."""
import io, json, zipfile
from pathlib import Path
import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

NB = Path(__file__).resolve().parents[1] / "notebooks" / "04_gtfs_frequency.ipynb"


@pytest.fixture(scope="module")
def ns():
    cells = json.load(open(NB))["cells"]
    ns = {}
    for c in cells:
        s = "".join(c["source"])
        if c["cell_type"] == "code" and ("def active_trips" in s or s.startswith("from pathlib")):
            exec(s.replace('print(GTFS.exists()', '#'), ns)
    ns["CHUNK"] = 7        # force several chunks
    return ns


def feed():
    files = {
        "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
                        "WK,1,1,1,1,1,0,0,20261001,20261231\nSAT,0,0,0,0,0,1,0,20261001,20261231\n",
        "calendar_dates.txt": "service_id,date,exception_type\nWK,20261006,2\nEXTRA,20261006,1\n",   # WK removed on the test Tuesday, EXTRA added
        "trips.txt": "trip_id,service_id\nw1,WK\nw2,WK\ne1,EXTRA\ne2,EXTRA\ns1,SAT\n",
        "stops.txt": "stop_id,stop_lat,stop_lon\nA,51.5,-0.1\nB,52.5,-1.9\n",
        "stop_times.txt": "trip_id,stop_id,departure_time\n"
                          "w1,A,08:00:00\nw2,A,08:30:00\n"                                  # weekday trips (not running on 6 Oct: removed)
                          "e1,A,08:10:00\ne1,B,12:00:00\ne2,A,17:00:00\ne2,A,25:30:00\n"    # EXTRA: morning A, off-peak B, evening A, 01:30 next day (ignored)
                          "s1,A,09:00:00\ns1,B,09:30:00\ns1,B,09:45:00\n",
    }
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for k, v in files.items():
            z.writestr(k, v)
    return zipfile.ZipFile(io.BytesIO(b.getvalue()))


def test_active_trips_respects_calendar_exceptions(ns):
    z = feed()
    assert ns["active_trips"](z, "2026-10-06") == {"e1", "e2"}      # Tuesday: WK removed, EXTRA added
    assert ns["active_trips"](z, "2026-10-07") == {"w1", "w2"}      # normal Wednesday
    assert ns["active_trips"](z, "2026-10-10") == {"s1"}            # Saturday
    assert ns["active_trips"](z, "2026-10-11") == set()             # Sunday: nothing


def test_departures_by_stop_counts_each_day_and_band(ns):
    z = feed()
    act = {"weekday": ns["active_trips"](z, "2026-10-06"), "saturday": ns["active_trips"](z, "2026-10-10")}
    dep = {k: v.set_index("stop_id") for k, v in ns["departures_by_stop"](z, act).items()}
    assert dep["weekday"].loc["A", "morning"] == 1 and dep["weekday"].loc["A", "evening"] == 1
    assert dep["weekday"].loc["B", "off_peak"] == 1
    assert dep["weekday"]["morning"].get("B", 0) == 0
    assert dep["weekday"].sum().sum() == 3                          # the 25:30 departure (01:30) falls outside every band
    assert dep["saturday"].loc["A", "morning"] == 1 and dep["saturday"].loc["B", "morning"] == 2


def test_lsoa_frequency_per_hour(ns):
    z = feed()
    act = {"saturday": ns["active_trips"](z, "2026-10-10")}
    dep = ns["departures_by_stop"](z, act)["saturday"]
    lsoa = gpd.GeoDataFrame({"LSOA21CD": ["E1", "E2", "E3"]}, geometry=[box(-1, 51, 0, 52), box(-3, 52, -1, 53), box(5, 5, 6, 6)], crs=4326).to_crs(27700)
    base = pd.DataFrame({"LSOA21CD": ["E1", "E2", "E3"]})
    f = ns["lsoa_frequency"](z, dep, lsoa, base).set_index("LSOA21CD")
    assert f.loc["E1", "freq_morning"] == pytest.approx(1 / 3)       # 1 departure in the 3-hour morning band
    assert f.loc["E2", "freq_morning"] == pytest.approx(2 / 3)
    assert f.loc["E3"].sum() == 0                                    # no service -> 0, not missing
