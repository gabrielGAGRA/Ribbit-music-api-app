import type { ProviderToken } from '@angular/core';
import { inject } from '@angular/core';

export function safeInject<T>(token: ProviderToken<T>, fallback: T): T {
  try {
    return inject(token, { optional: true }) ?? fallback;
  } catch {
    // Allow instantiating outside an Angular injection context in isolated unit tests
    return fallback;
  }
}
