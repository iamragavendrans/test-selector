Feature: Division Operation
  As a calculator API consumer
  I want to divide two numbers
  So that I can get the correct quotient

  @smoke @happy_path @critical
  Scenario: Divide two positive integers
    Given the calculator API is running
    When I send a POST request to "/divide" with body {"a": 20, "b": 5}
    Then the response status should be 200
    And the response "result" should equal 4
    And the response "error" should equal null

  @regression @happy_path
  Scenario Outline: Divide various number combinations
    Given the calculator API is running
    When I send a POST request to "/divide" with body {"a": <a>, "b": <b>}
    Then the response status should be 200
    And the response "result" should equal <expected>
    And the response "error" should equal null

    Examples:
      | a    | b   | expected |
      | 0    | 5   | 0        |
      | -12  | 3   | -4       |
      | -9   | -3  | 3        |
      | 7.5  | 2.5 | 3.0      |
      | 100  | 4   | 25       |

  @negative @edge_case @critical
  Scenario: Divide by zero should return friendly error
    Given the calculator API is running
    When I send a POST request to "/divide" with body {"a": 5, "b": 0}
    Then the response status should be 200
    And the response "result" should equal null
    And the response "error" should equal "Division by zero"
