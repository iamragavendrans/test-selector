import { test, expect } from '../../framework/fixtures/test-fixtures';
import { ENV } from '../../framework/config/env';
import { LoginPage } from '../../framework/pages/login.page';

test.describe('OrangeHRM UI + ReqRes API e2e @e2e @ui @api @critical', () => {
  test('login in OrangeHRM then verify API users endpoint', async ({ page, reqresClient }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto(ENV.orangehrmUrl);
    await loginPage.login(ENV.orangehrmUsername, ENV.orangehrmPassword);
    await loginPage.assertDashboardVisible();

    const apiRes = await reqresClient.listUsers(2);
    expect(apiRes.status()).toBe(200);
    const body = await apiRes.json();
    expect(body.page).toBe(2);
  });
});
