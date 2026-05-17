import os

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


class Endpoints:
    ADD = f"{BASE_URL}/add"
    SUBTRACT = f"{BASE_URL}/subtract"
    MULTIPLY = f"{BASE_URL}/multiply"
    DIVIDE = f"{BASE_URL}/divide"
    POWER = f"{BASE_URL}/power"
    SQRT = f"{BASE_URL}/sqrt"
    HEALTH = f"{BASE_URL}/health"


class ResponseFields:
    RESULT = "result"
    ERROR = "error"
    STATUS = "status"


class StatusCodes:
    OK = 200
    UNPROCESSABLE = 422


class Defaults:
    LOG_FILE = "tests/test_run_log.jsonl"
    SMOKE_LOG_FILE = "tests/smoke_run_log.jsonl"
    COMMIT_SHA_ENV = "GIT_COMMIT_SHA"
    CHANGED_FILES_ENV = "GIT_CHANGED_FILES"
