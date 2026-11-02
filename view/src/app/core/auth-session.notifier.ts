import { Injectable } from '@angular/core';

type UnauthorizedListener = () => void;

/** Broadcasts 401 session invalidation events without circular DI dependencies. */
@Injectable({ providedIn: 'root' })
export class AuthSessionNotifier {
  private readonly listeners = new Set<UnauthorizedListener>();

  /** Registers a listener invoked when a protected endpoint returns 401. */
  onUnauthorized(listener: UnauthorizedListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /** Notifies all subscribers that the current token is no longer valid. */
  notifyUnauthorized(): void {
    for (const listener of this.listeners) {
      listener();
    }
  }
}
