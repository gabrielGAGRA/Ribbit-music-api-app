import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';
import { AdminModerationComponent } from './admin-moderation.component';
import { AdminStateService } from './admin-state.service';

describe('AdminModerationComponent', () => {
  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({});
  });

  it('searches active tracks, toggles explicit/+18, blocks/restores tracks, and deletes reviews', () => {
    const state = TestBed.inject(AdminStateService);
    const component = TestBed.runInInjectionContext(() => new AdminModerationComponent());

    expect(component['formatDuration'](218)).toBe('3:38');
    expect(component['searchedActiveTracks']().length).toBe(5);

    component['trackQuery'].set('Boogarins');
    expect(component['searchedActiveTracks']().length).toBe(1);

    const targetTrack = component['searchedActiveTracks']()[0]!;
    expect(targetTrack.explicit).toBe(false);
    component['toggleExplicit'](targetTrack);
    expect(state.activeTracks().find((item) => item.track_id === 107)?.explicit).toBe(true);

    component['blockTrack'](107);
    expect(component['blockedTracks']().some((item) => item.track_id === 107)).toBe(true);

    component['selectTab']('blocked');
    component['restoreTrack'](107);
    expect(component['blockedTracks']().some((item) => item.track_id === 107)).toBe(false);

    component['selectTab']('reviews');
    const reviewCount = component['topReviews']().length;
    component['removeReview'](502);
    expect(component['topReviews']().length).toBe(reviewCount - 1);
  });
});
