Feature: Square Root Operation
  As a calculator API consumer
  I want to calculate square roots
  So that I can get principal root results

  @smoke @happy_path @critical
  Scenario: Square root of a perfect square
    Given the calculator API is running
    When I send a POST request to "/sqrt" with body {"a": 49}
    Then the response status should be 200
    And the response "result" should equal 7
    And the response "error" should equal null

  @regression @happy_path
  Scenario Outline: Square root of valid values
    Given the calculator API is running
    When I send a POST request to "/sqrt" with body {"a": <a>}
    Then the response status should be 200
    And the response "result" should equal <expected>
    And the response "error" should equal null

    Examples:
      | a    | expected |
      | 0    | 0        |
      | 1    | 1        |
      | 4    | 2        |
      | 2.25 | 1.5      |
      | 100  | 10       |

  @negative @edge_case @critical
  Scenario: Square root of negative number should return friendly error
    Given the calculator API is running
    When I send a POST request to "/sqrt" with body {"a": -9}
    Then the response status should be 200
    And the response "result" should equal null
    And the response "error" should equal "Cannot sqrt negative"
