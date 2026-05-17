Feature: Addition Operation
  As a calculator API consumer
  I want to add two numbers
  So that I can get the correct sum

  @smoke @happy_path @critical @addition
  Scenario: Add two positive integers
    Given the calculator API is running
    When I send a POST request to "/add" with body {"a": 3, "b": 5}
    Then the response status should be 200
    And the response "result" should equal 8

  @regression @happy_path @addition
  Scenario Outline: Add various number combinations
    Given the calculator API is running
    When I send a POST request to "/add" with body {"a": <a>, "b": <b>}
    Then the response status should be 200
    And the response "result" should equal <expected>

    Examples:
      | a    | b    | expected |
      | 0    | 0    | 0        |
      | -5   | 5    | 0        |
      | -3   | -4   | -7       |
      | 1.5  | 2.5  | 4.0      |
      | 100  | 200  | 300      |

  @edge_case @regression @addition
  Scenario: Add very large numbers
    Given the calculator API is running
    When I send a POST request to "/add" with body {"a": 999999999, "b": 1}
    Then the response status should be 200
    And the response "result" should equal 1000000000
