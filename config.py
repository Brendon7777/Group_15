import os


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Africa/Johannesburg")
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False


class DevelopmentConfig(BaseConfig):
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-change-me"
    DEBUG = os.environ.get("FLASK_DEBUG") == "1"


class TestingConfig(BaseConfig):
    SECRET_KEY = os.environ.get("SECRET_KEY") or "test-only-change-me"
    TESTING = True


class ProductionConfig(BaseConfig):
    SESSION_COOKIE_SECURE = True


def config_for_environment(name):
    configs = {
        "development": DevelopmentConfig,
        "test": TestingConfig,
        "testing": TestingConfig,
        "production": ProductionConfig,
    }
    try:
        config = configs[name]
    except KeyError as error:
        raise RuntimeError(
            "APP_ENV must be development, test, testing, or production."
        ) from error

    if config is ProductionConfig and not os.environ.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY must be set when APP_ENV=production (see .env.example)."
        )
    return config
