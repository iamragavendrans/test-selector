Feature: ReqRes API scenarios
  Scenario: List users
    Given ReqRes API is reachable
    When users are requested for page 2
    Then user data should be returned

  Scenario: User not found
    Given ReqRes API is reachable
    When non-existent user is requested
    Then API should return 404
