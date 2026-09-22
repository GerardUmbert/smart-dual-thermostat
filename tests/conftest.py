"""Make the integration's pure-logic modules importable without Home Assistant.

const.py, season.py and quirks.py have no dependency on the
`homeassistant` package, but they live inside a component package whose
__init__.py does import it. Rather than requiring the full homeassistant
dependency tree just to test these three files, register a lightweight
fake package pointing at the component directory and load each module
from its file path into it, so `from .const import ...` (relative
imports) resolve normally.
"""
import importlib.util
import sys
import types
from pathlib import Path

COMPONENT_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "smart_dual_thermostat"
PACKAGE_NAME = "smart_dual_thermostat"

if PACKAGE_NAME not in sys.modules:
    fake_package = types.ModuleType(PACKAGE_NAME)
    fake_package.__path__ = [str(COMPONENT_DIR)]
    sys.modules[PACKAGE_NAME] = fake_package

    for module_name in ("const", "quirks", "season"):
        spec = importlib.util.spec_from_file_location(
            f"{PACKAGE_NAME}.{module_name}", COMPONENT_DIR / f"{module_name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
