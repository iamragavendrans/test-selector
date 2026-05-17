Feature: Health Endpoint
  As a platform engineer
  I want a health endpoint
  So that I can verify service readiness and liveness

  @smoke @happy_path @critical @health
  Scenario: Health endpoint returns service status
    Given the calculator API is running
    When I send a GET request to "/health"
    Then the response status should be 200
    And the response "status" should equal "ok"

  @regression @happy_path @health
  Scenario Outline: Health endpoint remains stable across repeated checks
    Given the calculator API is running
    When I send a GET request to "/health"
    Then the response status should be 200
    And the response "status" should equal "ok"

    Examples:
      | run |
      | 1   |
      | 2   |
      | 3   |
      | 4   |
      | 5   |

  @regression @critical @health
  Scenario: Health endpoint response contains only expected status
    Given the calculator API is running
    When I send a GET request to "/health"
    Then the response status should be 200
    And the response "status" should equal "ok"
