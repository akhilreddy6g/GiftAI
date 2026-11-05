import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { APP_CONFIG } from '../config/app-config';
import { ApiError } from './api-error';
import type { HttpMethod, PathsWith, RequestOptions, SuccessBody } from './api-types';

/**
 * Calls the GiftAI API with request and response types taken from its OpenAPI schema.
 * Sign-in tokens are added by the auth interceptor; failures reject with ``ApiError``.
 */
@Injectable({ providedIn: 'root' })
export class ApiClient {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = inject(APP_CONFIG).apiUrl;

  get<P extends PathsWith<'get'>>(path: P, options: RequestOptions<P, 'get'>) {
    return this.send<P, 'get'>('get', path, options);
  }

  post<P extends PathsWith<'post'>>(path: P, options: RequestOptions<P, 'post'>) {
    return this.send<P, 'post'>('post', path, options);
  }

  patch<P extends PathsWith<'patch'>>(path: P, options: RequestOptions<P, 'patch'>) {
    return this.send<P, 'patch'>('patch', path, options);
  }

  delete<P extends PathsWith<'delete'>>(path: P, options: RequestOptions<P, 'delete'>) {
    return this.send<P, 'delete'>('delete', path, options);
  }

  /** True for URLs this client calls, so interceptors leave other hosts alone. */
  isApiUrl(url: string): boolean {
    return url === this.baseUrl || url.startsWith(`${this.baseUrl}/`);
  }

  private async send<P extends PathsWith<M>, M extends HttpMethod>(
    method: M,
    path: P,
    options: RequestOptions<P, M>,
  ): Promise<SuccessBody<P, M>> {
    const {
      path: pathParams,
      query,
      body,
    } = options as {
      path?: Record<string, string>;
      query?: Record<string, string | number | boolean | null | undefined>;
      body?: unknown;
    };
    const url = this.baseUrl + fillPath(path, pathParams ?? {});
    try {
      return await firstValueFrom(
        this.http.request<SuccessBody<P, M>>(method.toUpperCase(), url, {
          body,
          params: withoutEmpty(query ?? {}),
        }),
      );
    } catch (error) {
      throw ApiError.from(error);
    }
  }
}

function fillPath(template: string, params: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (_, name: string) => {
    const value = params[name];
    if (value === undefined) throw new Error(`Missing path parameter "${name}" for ${template}`);
    return encodeURIComponent(value);
  });
}

function withoutEmpty(
  query: Record<string, string | number | boolean | null | undefined>,
): Record<string, string | number | boolean> {
  const params: Record<string, string | number | boolean> = {};
  for (const [key, value] of Object.entries(query)) {
    if (value !== null && value !== undefined) params[key] = value;
  }
  return params;
}
