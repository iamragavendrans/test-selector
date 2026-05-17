import { APIRequestContext, APIResponse } from '@playwright/test';

export class ReqResClient {
  constructor(
    private readonly request: APIRequestContext,
    private readonly baseUrl: string,
    private readonly apiKey = ''
  ) {}

  private headers(): Record<string, string> {
    return this.apiKey ? { 'x-api-key': this.apiKey } : {};
  }

  listUsers(page = 2): Promise<APIResponse> {
    return this.request.get(`${this.baseUrl}/users?page=${page}`, { headers: this.headers() });
  }

  getUser(id: number): Promise<APIResponse> {
    return this.request.get(`${this.baseUrl}/users/${id}`, { headers: this.headers() });
  }

  createUser(name: string, job: string): Promise<APIResponse> {
    return this.request.post(`${this.baseUrl}/users`, {
      headers: this.headers(),
      data: { name, job }
    });
  }
}
