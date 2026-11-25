"""Run this once to confirm the tools are installed: python check_setup.py"""
import importlib, sys

print("Python", sys.version.split()[0])
if sys.version_info < (3, 11):
    print("WARNING: Python 3.11 or newer is recommended.")

modules = ["pandas", "geopandas", "shapely", "pyproj", "sklearn", "pulp",
           "matplotlib", "plotly", "streamlit", "folium", "pyarrow"]
missing = []
for m in modules:
    try:
        mod = importlib.import_module(m)
        print(f"OK       {m} {getattr(mod, '__version__', '')}")
    except ImportError:
        print(f"MISSING  {m}")
        missing.append(m)

print("\nAll good." if not missing else "\nInstall the missing packages: pip install -r requirements-full.txt")
