Feature: OrangeHRM UI scenarios
  Scenario: Login with valid credentials
    Given user opens login page
    When user submits valid credentials
    Then dashboard is shown
