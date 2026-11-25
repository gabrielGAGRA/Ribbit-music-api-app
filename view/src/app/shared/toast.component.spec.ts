import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';
import { RibbitStateService } from '../core/ribbit-state.service';
import { ToastComponent } from './toast.component';

describe('ToastComponent', () => {
  it('reads toast state from RibbitStateService', () => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    const state = TestBed.inject(RibbitStateService);
    const component = TestBed.runInInjectionContext(() => new ToastComponent());
    state.toast.set('Operação concluída');
    expect(component['state'].toast()).toBe('Operação concluída');
    component['closeToast']();
    expect(state.toast()).toBe('');
  });
});
