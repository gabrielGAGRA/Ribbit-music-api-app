import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { NO_ERRORS_SCHEMA } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { RibbitStateService } from '../core/ribbit-state.service';
import { RibbyAlertComponent } from './ribby-alert.component';

describe('RibbyAlertComponent', () => {
  let state: RibbitStateService;

  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    const html = readFileSync(resolve(__dirname, './ribby-alert.component.html'), 'utf8');
    TestBed.overrideComponent(RibbyAlertComponent, {
      set: {
        template: html,
        templateUrl: undefined,
        styleUrl: undefined,
        styles: [],
        imports: [],
        schemas: [NO_ERRORS_SCHEMA],
      },
    });
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    state = TestBed.inject(RibbitStateService);
  });

  afterEach(() => {
    vi.useRealTimers();
    state?.ngOnDestroy();
  });

  it('renders speech bubble when state.ribbyAlert() is set and dismisses on click or close button', () => {
    const fixture = TestBed.createComponent(RibbyAlertComponent);
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.ribby-alert-card')).toBeNull();

    state.showRibbyAlert({
      title: 'Conteúdo restrito para menores',
      message: 'Faixa bloqueada para menores de 18 anos.',
      tone: 'restriction',
      mood: 'talk',
    });
    fixture.detectChanges();

    const card = fixture.nativeElement.querySelector('.ribby-alert-card');
    expect(card).not.toBeNull();
    expect(card instanceof HTMLElement).toBe(true);
    if (!(card instanceof HTMLElement)) return;
    expect(card.classList.contains('tone-restriction')).toBe(true);
    expect(card.textContent).toContain('Conteúdo restrito para menores');
    expect(card.textContent).toContain('Faixa bloqueada para menores de 18 anos.');

    const closeBtn = fixture.nativeElement.querySelector('.ribby-alert-close');
    expect(closeBtn instanceof HTMLButtonElement).toBe(true);
    if (!(closeBtn instanceof HTMLButtonElement)) return;
    closeBtn.click();
    fixture.detectChanges();

    expect(state.ribbyAlert()).toBeNull();
    expect(fixture.nativeElement.querySelector('.ribby-alert-card')).toBeNull();
  });

  it('applies review and plan tone classes and pauses auto-dismiss on hover', () => {
    const fixture = TestBed.createComponent(RibbyAlertComponent);
    state.showRibbyAlert({
      title: 'Você já avaliou esta música',
      message: 'Exclua sua avaliação atual para enviar outra.',
      tone: 'review',
      mood: 'talk',
      durationMs: 6000,
    });
    fixture.detectChanges();

    const card = fixture.nativeElement.querySelector('.ribby-alert-card');
    expect(card instanceof HTMLElement).toBe(true);
    if (!(card instanceof HTMLElement)) return;
    expect(card.classList.contains('tone-review')).toBe(true);

    card.dispatchEvent(new MouseEvent('mouseenter'));
    vi.advanceTimersByTime(7000);
    expect(state.ribbyAlert()).not.toBeNull();

    card.dispatchEvent(new MouseEvent('mouseleave'));
    vi.advanceTimersByTime(3600);
    expect(state.ribbyAlert()).toBeNull();

    state.showRibbyAlert({
      title: 'Recurso dos planos pagos',
      message: 'Disponível no Ribbit Pro.',
      tone: 'plan',
      mood: 'wave',
    });
    fixture.detectChanges();
    const planCard = fixture.nativeElement.querySelector('.ribby-alert-card');
    expect(planCard instanceof HTMLElement && planCard.classList.contains('tone-plan')).toBe(true);
  });
});
