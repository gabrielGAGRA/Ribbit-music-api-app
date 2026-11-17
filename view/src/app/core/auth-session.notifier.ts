import { Injectable } from '@angular/core';

type UnauthorizedListener = () => void;

/** Broadcasts 401 session invalidation events without circular DI dependencies. */
@Injectable({ providedIn: 'root' })
export class AuthSessionNotifier {
  private readonly listeners = new Set<UnauthorizedListener>();
  private readonly adminListeners = new Set<UnauthorizedListener>();

  /** Registers a listener invoked when a protected listener endpoint returns 401. */
  onUnauthorized(listener: UnauthorizedListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /** Registers a listener invoked when a protected admin endpoint returns 401. */
  onAdminUnauthorized(listener: UnauthorizedListener): () => void {
    this.adminListeners.add(listener);
    return () => {
      this.adminListeners.delete(listener);
    };
  }

  /** Notifies all listener subscribers that the current token is no longer valid. */
  notifyUnauthorized(): void {
    for (const listener of this.listeners) {
      listener();
    }
  }

  /** Notifies all admin subscribers that the current admin token is no longer valid. */
  notifyAdminUnauthorized(): void {
    for (const listener of this.adminListeners) {
      listener();
    }
  }
}
