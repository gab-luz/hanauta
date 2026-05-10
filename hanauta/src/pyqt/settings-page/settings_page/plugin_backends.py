import importlib.util
from pathlib import Path


def load_plugin_backend(module_name: str, candidates: list[Path]):
    for candidate in candidates:
        if not candidate.exists():
            continue
        spec = importlib.util.spec_from_file_location(module_name, candidate)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        __importlib__sys_modules = __import("sys").modules
        __importlib__sys_modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    raise ImportError(f"Unable to load plugin backend {module_name}: {candidates}")


THIS_FILE = Path(__file__).resolve()


def _project_root_candidates() -> list[Path]:
    candidates: list[Path] = []
    # Typical checkout layout: <root>/hanauta/src/pyqt/settings-page/settings_page
    for idx in (5, 4, 3):
        try:
            candidates.append(THIS_FILE.parents[idx])
        except Exception:
            pass
    # Common live i3 path.
    candidates.append(Path.home() / ".config" / "i3")
    # Dev fallback.
    candidates.append(Path.home() / "dev" / "hanauta")
    ordered: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(candidate)
    return ordered


ROOT_CANDIDATES = _project_root_candidates()


def _plugin_candidates(plugin_dir: str, backend_name: str) -> list[Path]:
    paths: list[Path] = []
    for root in ROOT_CANDIDATES:
        paths.append(root / "hanauta" / "src" / "pyqt" / plugin_dir / backend_name)
        paths.append(root / "src" / "pyqt" / plugin_dir / backend_name)
    return paths

GAMEMODE_CANDIDATES = _plugin_candidates(
    "plugin-gamemode", "gamemode_backend.py"
) + [Path.home() / "dev" / "hanauta-plugin-game-mode" / "gamemode_backend.py"]

try:
    _GAMEMODE_BACKEND = load_plugin_backend("hanauta_plugin_gamemode_backend", GAMEMODE_CANDIDATES)
    gamemode_summary = _GAMEMODE_BACKEND.summary
except Exception:
    def gamemode_summary() -> str:
        return "GameMode unavailable"


WEATHER_CANDIDATES = _plugin_candidates("plugin-weather", "weather_backend.py") + [
    Path.home() / "dev" / "hanauta-plugin-weather" / "weather_backend.py"
]


def _fallback_configured_city(_settings: object = None) -> None:  # type: ignore[no-redef]
    return None


def _fallback_search_cities(_query: str) -> list:  # type: ignore[no-redef]
    return []


WeatherCity = None
configured_city = _fallback_configured_city
search_cities = _fallback_search_cities

try:
    _WEATHER_BACKEND = load_plugin_backend("hanauta_plugin_weather_backend", WEATHER_CANDIDATES)
    WeatherCity = _WEATHER_BACKEND.WeatherCity
    configured_city = _WEATHER_BACKEND.configured_city
    search_cities = _WEATHER_BACKEND.search_cities
except Exception:
    pass


HOME_ASSISTANT_CANDIDATES = _plugin_candidates(
    "plugin-home-assistant", "home_assistant_backend.py"
) + [Path.home() / "dev" / "hanauta-plugin-home-assistant" / "home_assistant_backend.py"]


def _fallback_entity_friendly_name(entity_id: str, _settings: dict | None = None) -> str:
    return entity_id


def _fallback_entity_icon_name(entity_id: str) -> str:
    return ""


def _fallback_entity_secondary_text(entity_state: dict) -> str:
    return ""


def _fallback_prefetch_entity_icons(entity_ids: list[str]) -> None:
    pass


entity_friendly_name = _fallback_entity_friendly_name
entity_icon_name = _fallback_entity_icon_name
entity_secondary_text = _fallback_entity_secondary_text
prefetch_entity_icons = _fallback_prefetch_entity_icons

try:
    _HOME_ASSISTANT_BACKEND = load_plugin_backend(
        "hanauta_plugin_home_assistant_backend", HOME_ASSISTANT_CANDIDATES
    )
    entity_friendly_name = _HOME_ASSISTANT_BACKEND.entity_friendly_name
    entity_icon_name = _HOME_ASSISTANT_BACKEND.entity_icon_name
    entity_secondary_text = _HOME_ASSISTANT_BACKEND.entity_secondary_text
    prefetch_entity_icons = _HOME_ASSISTANT_BACKEND.prefetch_entity_icons
except Exception:
    pass
