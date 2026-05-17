Feature: Power Operation
  As a calculator API consumer
  I want to raise a number to a power
  So that I can compute exponents correctly

  @smoke @happy_path @critical @power
  Scenario: Raise positive integer to power
    Given the calculator API is running
    When I send a POST request to "/power" with body {"a": 2, "b": 3}
    Then the response status should be 200
    And the response "result" should equal 8

  @regression @happy_path @power
  Scenario Outline: Compute power with varied inputs
    Given the calculator API is running
    When I send a POST request to "/power" with body {"a": <a>, "b": <b>}
    Then the response status should be 200
    And the response "result" should equal <expected>

    Examples:
      | a   | b   | expected |
      | 5   | 0   | 1        |
      | -2  | 3   | -8       |
      | -2  | 2   | 4        |
      | 9   | 0.5 | 3.0      |
      | 1.5 | 2   | 2.25     |

  @edge_case @regression @power
  Scenario: Raise zero to positive power
    Given the calculator API is running
    When I send a POST request to "/power" with body {"a": 0, "b": 5}
    Then the response status should be 200
    And the response "result" should equal 0
