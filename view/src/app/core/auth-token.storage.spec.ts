import { beforeEach, describe, expect, it } from 'vitest';
import {
  clearAdminAuthToken,
  clearAuthStorage,
  readAdminAuthToken,
  readAuthToken,
  writeAdminAuthToken,
  writeAuthToken,
} from './auth-token.storage';

describe('auth-token.storage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('persists and clears user and admin auth tokens', () => {
    writeAuthToken('user-jwt');
    writeAdminAuthToken('admin-jwt');
    expect(readAuthToken()).toBe('user-jwt');
    expect(readAdminAuthToken()).toBe('admin-jwt');

    clearAuthStorage();
    clearAdminAuthToken();
    expect(readAuthToken()).toBeNull();
    expect(readAdminAuthToken()).toBeNull();
  });
});
