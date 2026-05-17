import { expect, test } from '@playwright/test';

type ReqResUser = { id: number; email: string };

const parseUsers = (payload: { data: ReqResUser[] }) => payload.data.map((u) => u.id);
const isValidEmail = (email: string) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email);

test.describe('ReqRes helper unit tests @unit @api', () => {
  test('extract user ids', async () => {
    expect(parseUsers({ data: [{ id: 2, email: 'a@b.com' }, { id: 7, email: 'b@c.com' }] })).toEqual([2, 7]);
  });

  test('email validator', async () => {
    expect(isValidEmail('janet.weaver@reqres.in')).toBeTruthy();
    expect(isValidEmail('broken-email')).toBeFalsy();
  });
});
