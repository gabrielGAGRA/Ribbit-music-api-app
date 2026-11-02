import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';
import { ProfileComponent } from './profile.component';
import { authInterceptor } from '../../core/auth.interceptor';
import { RibbitStateService } from '../../core/ribbit-state.service';

describe('ProfileComponent', () => {
  let component: ProfileComponent;
  let state: RibbitStateService;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    state = TestBed.inject(RibbitStateService);
    component = TestBed.runInInjectionContext(() => new ProfileComponent());
  });

  it('should switch between like, love, and reject tabs', () => {
    expect(component.selectedTab()).toBe('like');
    component.selectTab('love');
    expect(component.selectedTab()).toBe('love');
  });

  it('should calculate real counts from state collections', () => {
    expect(component.likeCount()).toBe(0);
    state.decide('love');
    expect(component.likeCount()).toBe(1);
    expect(component.loveCount()).toBe(1);
    state.decide('reject');
    expect(component.rejectCount()).toBe(1);
  });

  it('should cancel subscription to free plan', () => {
    state.setPlan('Individual');
    expect(state.currentPlan()).toBe('Individual');

    component.cancelSubscription();
    expect(state.currentPlan()).toBe('Free');
    expect(state.toast()).toContain('cancelada');
  });

  it('should set page to settings on goToSettings', () => {
    component.goToSettings();
    expect(state.activePage()).toBe('settings');
  });

  it('should stack profile account management, collections toolbar, and dashboard columns on mobile', () => {
    const globalStyles = readFileSync(resolve(__dirname, '../../../styles.css'), 'utf8');

    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*768px\)[\s\S]*\.account-management\s*\{[^}]*flex-direction:\s*column/,
    );
    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*768px\)[\s\S]*\.collection-toolbar\s*\{[^}]*flex-direction:\s*column/,
    );
    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*768px\)[\s\S]*\.dashboard-columns\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/,
    );
  });
});
