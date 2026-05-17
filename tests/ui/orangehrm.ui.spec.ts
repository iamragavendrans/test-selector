import { test } from '@playwright/test';
import { ENV } from '../../framework/config/env';
import { LoginPage } from '../../framework/pages/login.page';

test.describe('OrangeHRM UI scenarios @ui @scenario @smoke', () => {
  test('login and dashboard visible', async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto(ENV.orangehrmUrl);
    await loginPage.login(ENV.orangehrmUsername, ENV.orangehrmPassword);
    await loginPage.assertDashboardVisible();
  });
});
