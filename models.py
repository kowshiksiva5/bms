from dataclasses import dataclass, field
from typing import List, Optional, Set


@dataclass
class Movie:
    name: str
    url: Optional[str] = None


@dataclass
class Theatre:
    name: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    showtimes: List[str] = field(default_factory=list)


@dataclass
class Preferences:
    city: str = "Hyderabad"
    home_lat: Optional[float] = None
    home_lon: Optional[float] = None
    saved_theatres: List[str] = field(default_factory=list)


@dataclass
class WatchConfig:
    movie_name: str
    theatres: List[str]
    city: str = "Hyderabad"
    time_start: Optional[str] = None  # "HH:MM"
    time_end: Optional[str] = None    # "HH:MM"
    email: Optional[str] = None
    state_key: Optional[str] = None


