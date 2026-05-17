import { test, expect } from '../../framework/fixtures/test-fixtures';

test.describe('ReqRes API scenarios @api @scenario @critical', () => {
  test('list users page 2', async ({ reqresClient }) => {
    const res = await reqresClient.listUsers(2);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.page).toBe(2);
    expect(Array.isArray(body.data)).toBeTruthy();
  });

  test('get single user', async ({ reqresClient }) => {
    const res = await reqresClient.getUser(2);
    const body = await ReqResAssertions.expectStatusAndJson(res, 200);
    expect(body.data.id).toBe(2);
  });

  test('user not found', async ({ reqresClient }) => {
    const res = await reqresClient.getUser(23);
    expect(res.status()).toBe(404);
  });

  test('create user', async ({ reqresClient }) => {
    const res = await reqresClient.createUser('morpheus', 'leader');
    const body = await ReqResAssertions.expectStatusAndJson(res, 201);
    expect(body.name).toBe('morpheus');
  });
});

class ReqResAssertions {
  static async expectStatusAndJson(res: import('@playwright/test').APIResponse, status: number) {
    expect(res.status()).toBe(status);
    return res.json();
  }
}
