import { inject, ProviderToken } from '@angular/core';

export function safeInject<T>(token: ProviderToken<T>, fallback: T): T {
  try {
    return inject(token, { optional: true }) ?? fallback;
  } catch {
    return fallback;
  }
}
