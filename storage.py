from __future__ import annotations
import json
import os
from typing import Dict, List, Optional, Set


from config import get_config_path
DEFAULT_STORE = get_config_path()


def _load_store(path: str = DEFAULT_STORE) -> Dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_store(data: Dict, path: str = DEFAULT_STORE) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def get_saved_theatres(path: str = DEFAULT_STORE) -> List[str]:
    data = _load_store(path)
    return data.get('saved_theatres', [])


def add_saved_theatre(name: str, path: str = DEFAULT_STORE) -> None:
    data = _load_store(path)
    theatres = set(data.get('saved_theatres', []))
    theatres.add(name)
    data['saved_theatres'] = sorted(theatres)
    _save_store(data, path)


def remove_saved_theatre(name: str, path: str = DEFAULT_STORE) -> None:
    data = _load_store(path)
    theatres = set(data.get('saved_theatres', []))
    if name in theatres:
        theatres.remove(name)
    data['saved_theatres'] = sorted(theatres)
    _save_store(data, path)


def set_home_location(lat: float, lon: float, path: str = DEFAULT_STORE) -> None:
    data = _load_store(path)
    data['home_lat'] = lat
    data['home_lon'] = lon
    _save_store(data, path)


def get_home_location(path: str = DEFAULT_STORE) -> Optional[tuple]:
    data = _load_store(path)
    lat = data.get('home_lat')
    lon = data.get('home_lon')
    if lat is None or lon is None:
        return None
    return float(lat), float(lon)


def get_state(state_key: str, path: str = DEFAULT_STORE) -> Set[str]:
    data = _load_store(path)
    key = f"state_{state_key}"
    return set(data.get(key, []))


def set_state(state_key: str, values: Set[str], path: str = DEFAULT_STORE) -> None:
    data = _load_store(path)
    key = f"state_{state_key}"
    data[key] = sorted(values)
    _save_store(data, path)


