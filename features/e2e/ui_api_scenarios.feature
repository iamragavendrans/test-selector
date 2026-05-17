Feature: OrangeHRM + ReqRes end-to-end scenarios
  Scenario: UI login and API validation
    Given user logs in to OrangeHRM
    When ReqRes users endpoint is called
    Then UI dashboard and API assertions should pass
