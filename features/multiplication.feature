Feature: Multiplication Operation
  As a calculator API consumer
  I want to multiply two numbers
  So that I can get the correct product

  @smoke @happy_path @critical
  Scenario: Multiply two positive integers
    Given the calculator API is running
    When I send a POST request to "/multiply" with body {"a": 6, "b": 7}
    Then the response status should be 200
    And the response "result" should equal 42

  @regression @happy_path
  Scenario Outline: Multiply various number combinations
    Given the calculator API is running
    When I send a POST request to "/multiply" with body {"a": <a>, "b": <b>}
    Then the response status should be 200
    And the response "result" should equal <expected>

    Examples:
      | a    | b    | expected |
      | 0    | 99   | 0        |
      | -5   | 5    | -25      |
      | -3   | -4   | 12       |
      | 1.5  | 2.0  | 3.0      |
      | 100  | 200  | 20000    |

  @edge_case @regression
  Scenario: Multiply very large values
    Given the calculator API is running
    When I send a POST request to "/multiply" with body {"a": 1000000, "b": 1000000}
    Then the response status should be 200
    And the response "result" should equal 1000000000000
