import { inject } from '@angular/core';
import type { CanActivateFn, UrlTree } from '@angular/router';
import { Router } from '@angular/router';
import { AdminStateService } from './admin-state.service';

/** Redirects unauthenticated visitors from /admin/* routes to /admin/login. */
export const adminAuthGuard: CanActivateFn = (): boolean | UrlTree => {
  const adminState = inject(AdminStateService);
  const router = inject(Router);
  if (adminState.isAuthenticated()) {
    return true;
  }
  return router.createUrlTree(['/admin/login']);
};
