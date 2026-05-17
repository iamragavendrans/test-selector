import { test as base } from '@playwright/test';
import { ReqResClient } from '../api/reqres.client';
import { ENV } from '../config/env';

type AppFixtures = {
  reqresClient: ReqResClient;
};

export const test = base.extend<AppFixtures>({
  reqresClient: async ({ request }, use) => {
    await use(new ReqResClient(request, ENV.reqresBaseUrl, ENV.reqresApiKey));
  }
});

export { expect } from '@playwright/test';
