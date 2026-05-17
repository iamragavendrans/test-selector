Feature: Subtraction Operation
  As a calculator API consumer
  I want to subtract two numbers
  So that I can get the correct difference

  @smoke @happy_path @critical
  Scenario: Subtract two positive integers
    Given the calculator API is running
    When I send a POST request to "/subtract" with body {"a": 10, "b": 4}
    Then the response status should be 200
    And the response "result" should equal 6

  @regression @happy_path
  Scenario Outline: Subtract various number combinations
    Given the calculator API is running
    When I send a POST request to "/subtract" with body {"a": <a>, "b": <b>}
    Then the response status should be 200
    And the response "result" should equal <expected>

    Examples:
      | a    | b    | expected |
      | 0    | 0    | 0        |
      | -5   | 5    | -10      |
      | -3   | -4   | 1        |
      | 10.5 | 0.5  | 10.0     |
      | 200  | 100  | 100      |

  @edge_case @regression
  Scenario: Subtract resulting in negative output
    Given the calculator API is running
    When I send a POST request to "/subtract" with body {"a": 1, "b": 999}
    Then the response status should be 200
    And the response "result" should equal -998
