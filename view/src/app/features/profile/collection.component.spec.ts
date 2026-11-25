import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';
import { CollectionComponent } from './collection.component';
import { RibbitStateService } from '../../core/ribbit-state.service';

describe('CollectionComponent', () => {
  let component: CollectionComponent;
  let state: RibbitStateService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    state = TestBed.inject(RibbitStateService);
    component = TestBed.runInInjectionContext(() => new CollectionComponent());
  });

  it('filters liked songs by search query', () => {
    state.likedSongs.set([
      {
        trackId: 1,
        title: 'Midnight City',
        artist: 'M83',
        genre: 'Synthpop',
        time: '4:03',
        image: '',
        album: 'Hurry Up',
        year: '2011',
        match: 92,
      },
      {
        trackId: 2,
        title: 'Bloom',
        artist: 'Odesza',
        genre: 'Electronic',
        time: '3:15',
        image: '',
        album: 'In Return',
        year: '2014',
        match: 90,
      },
    ]);

    const input = document.createElement('input');
    input.value = 'odesza';
    component['updateSearchQuery']({ target: input } as unknown as Event);
    expect(component['filteredItems']().map((s) => s.title)).toEqual(['Bloom']);
  });

  it('computes kind-specific metadata, plays summary track, opens discovery, and revises items', () => {
    const song = {
      trackId: 10,
      title: 'Solar',
      artist: 'Prism',
      genre: 'Pop',
      time: '3:00',
      image: '',
      album: 'Light',
      year: '2024',
      match: 95,
      previewUrl: 'https://example.com/p.mp3',
    };

    expect(component['accentClass']()).toBe('green');
    expect(component['iconName']()).toBe('heart');
    expect(component['subtitle']()).toBe('músicas curtidas');
    expect(component['totalCount']()).toBe(0);

    component['runSummaryAction']();
    expect(state.toast()).toContain('vazia');

    state.likedSongs.set([song]);
    component['runSummaryAction']();
    expect(state.discoverySong()?.trackId).toBe(10);

    component['openSongInDiscovery'](song);
    expect(state.activePage()).toBe('discover');

    component['runItemAction'](song);
  });
});
