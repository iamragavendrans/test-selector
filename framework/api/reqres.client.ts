import { APIRequestContext, APIResponse, expect } from '@playwright/test';

export class ReqResClient {
  constructor(
    private readonly request: APIRequestContext,
    private readonly baseUrl: string
  ) {}

  listUsers(page = 2): Promise<APIResponse> {
    return this.request.get(`${this.baseUrl}/users?page=${page}`);
  }

  getUser(id: number): Promise<APIResponse> {
    return this.request.get(`${this.baseUrl}/users/${id}`);
  }

  createUser(name: string, job: string): Promise<APIResponse> {
    return this.request.post(`${this.baseUrl}/users`, { data: { name, job } });
  }

  static async expectOkJson(response: APIResponse): Promise<any> {
    expect(response.ok()).toBeTruthy();
    return response.json();
  }
}
