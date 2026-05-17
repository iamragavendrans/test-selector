import json

from behave import given, then, when
from pytest import approx
import requests

from features.locators.api_locators import Endpoints, ResponseFields, StatusCodes

ENDPOINT_MAP = {
    "/add": Endpoints.ADD,
    "/subtract": Endpoints.SUBTRACT,
    "/multiply": Endpoints.MULTIPLY,
    "/divide": Endpoints.DIVIDE,
    "/power": Endpoints.POWER,
    "/sqrt": Endpoints.SQRT,
    "/health": Endpoints.HEALTH,
}


@given("the calculator API is running")
def step_api_running(context):
    response = requests.get(Endpoints.HEALTH, timeout=2)
    assert response.status_code == StatusCodes.OK


@when('I send a POST request to "{endpoint}" with body {body}')
def step_post_request(context, endpoint, body):
    context.last_endpoint = endpoint
    context.response = requests.post(ENDPOINT_MAP[endpoint], json=json.loads(body), timeout=5)


@when('I send a GET request to "{endpoint}"')
def step_get_request(context, endpoint):
    context.last_endpoint = endpoint
    context.response = requests.get(ENDPOINT_MAP[endpoint], timeout=5)


@then("the response status should be {status_code:d}")
def step_status_code(context, status_code):
    assert context.response.status_code == status_code


@then('the response "{field}" should equal {expected}')
def step_response_field(context, field, expected):
    parsed = json.loads(expected)
    value = context.response.json().get(field)
    if isinstance(parsed, float):
        assert value == approx(parsed)
    else:
        assert value == parsed
