import { Injectable } from '@angular/core';

interface GoogleCredentialResponse {
  readonly credential?: string;
}

interface GooglePromptMomentNotification {
  readonly isNotDisplayed?: () => boolean;
  readonly isSkippedMoment?: () => boolean;
  readonly isDismissedMoment?: () => boolean;
  readonly getDismissedReason?: () => string;
}

interface GoogleAccountsId {
  readonly initialize: (config: {
    readonly client_id: string;
    readonly callback: (response: GoogleCredentialResponse) => void;
    readonly ux_mode?: 'popup' | 'redirect';
    readonly cancel_on_tap_outside?: boolean;
  }) => void;
  readonly prompt: (
    momentListener?: (notification?: GooglePromptMomentNotification) => void,
  ) => void;
  readonly renderButton?: (
    parent: HTMLElement,
    options: {
      readonly type?: 'standard' | 'icon';
      readonly theme?: 'outline' | 'filled_blue' | 'filled_black';
      readonly size?: 'large' | 'medium' | 'small';
      readonly text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin';
      readonly shape?: 'rectangular' | 'pill' | 'circle' | 'square';
    },
  ) => void;
}

interface GoogleGlobalScope {
  readonly google?: {
    readonly accounts?: {
      readonly id?: GoogleAccountsId;
    };
  };
}

export interface GooglePromptCallbacks {
  readonly container?: HTMLElement | null;
  readonly shouldIgnoreMoment?: () => boolean;
  readonly onCredential: (idToken: string) => void;
  readonly onFallbackRendered?: () => void;
  readonly onPromptUnavailable: (message: string) => void;
}

function getGoogleAccountsId(): GoogleAccountsId | null {
  // globalThis is augmented with optional Google Identity Services script globals when loaded
  const win = globalThis as GoogleGlobalScope;
  return win.google?.accounts?.id ?? null;
}

function isGooglePromptDismissed(notification: GooglePromptMomentNotification): boolean {
  return Boolean(
    notification.isDismissedMoment?.() &&
    notification.getDismissedReason?.() !== 'credential_returned',
  );
}

function isGooglePromptSuppressed(notification: GooglePromptMomentNotification): boolean {
  return Boolean(notification.isNotDisplayed?.() || notification.isSkippedMoment?.());
}

/** Encapsulates Google Identity Services (GIS) global script & DOM fallback rendering. */
@Injectable({ providedIn: 'root' })
export class GoogleIdentityService {
  private initializedClientId: string | null = null;
  private activeCredentialHandler: ((idToken: string) => void) | null = null;

  /** Validates whether a backend-provided Google OAuth authorization URL is safe to navigate to. */
  isValidAuthorizeUrl(rawUrl: unknown): rawUrl is string {
    if (typeof rawUrl !== 'string' || !rawUrl.trim()) {
      return false;
    }
    try {
      const parsed = new URL(rawUrl.trim());
      return parsed.protocol === 'https:' && parsed.hostname === 'accounts.google.com';
    } catch {
      return false;
    }
  }

  /** Navigates the browser window to a validated external OAuth URL. */
  navigateToExternalUrl(url: string): void {
    if (typeof window !== 'undefined') {
      window.location.assign(url);
    }
  }

  /** Initializes and prompts Google Identity Services, rendering the fallback button if needed. */
  promptSignIn(clientId: string, callbacks: GooglePromptCallbacks): void {
    const googleId = getGoogleAccountsId();
    if (!googleId) {
      callbacks.onPromptUnavailable('Serviço de autenticação do Google indisponível no navegador.');
      return;
    }

    this.activeCredentialHandler = callbacks.onCredential;
    if (this.initializedClientId !== clientId) {
      googleId.initialize({
        client_id: clientId,
        callback: (response) => {
          this.activeCredentialHandler?.(response.credential ?? '');
        },
        ux_mode: 'popup',
        cancel_on_tap_outside: true,
      });
      this.initializedClientId = clientId;
    }

    this.renderFallbackButton(googleId, callbacks.container, callbacks.onFallbackRendered);
    googleId.prompt((notification) => {
      if (!notification || callbacks.shouldIgnoreMoment?.()) {
        return;
      }
      if (isGooglePromptDismissed(notification)) {
        this.renderFallbackButton(googleId, callbacks.container, callbacks.onFallbackRendered);
        return;
      }
      if (
        isGooglePromptSuppressed(notification) &&
        !this.renderFallbackButton(googleId, callbacks.container, callbacks.onFallbackRendered)
      ) {
        callbacks.onPromptUnavailable(
          'Não foi possível exibir o modal do Google. Verifique as permissões do navegador.',
        );
      }
    });
  }

  private renderFallbackButton(
    googleId: GoogleAccountsId,
    container: HTMLElement | null | undefined,
    onFallbackRendered?: () => void,
  ): boolean {
    if (!googleId.renderButton || !container) {
      return false;
    }
    if (container.dataset['gsiRendered'] !== 'true') {
      googleId.renderButton(container, {
        type: 'standard',
        theme: 'outline',
        size: 'large',
        text: 'continue_with',
        shape: 'pill',
      });
      container.dataset['gsiRendered'] = 'true';
    }
    onFallbackRendered?.();
    container.classList.add('visible');
    container.focus();
    return true;
  }
}
