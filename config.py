import os
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(name, default)


def get_default_city_slug() -> str:
    return get_env('BMS_CITY_SLUG', 'hyderabad')


def get_email_defaults() -> tuple[str, str]:
    from_email = get_env('BMS_EMAIL_FROM', 'your_email@gmail.com')
    app_password = get_env('BMS_EMAIL_APP_PASSWORD', 'your_app_password')
    return from_email, app_password


def get_config_path() -> str:
    return get_env('BMS_CONFIG_PATH', os.path.expanduser('~/.bms_config.json'))


def get_chrome_binary() -> Optional[str]:
    return get_env('CHROME_BINARY') or get_env('CHROMIUM_BINARY')


