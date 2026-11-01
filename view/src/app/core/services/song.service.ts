import { Injectable, signal } from '@angular/core';
import { Observable, of } from 'rxjs';
import { delay, tap } from 'rxjs/operators';
import { Song, CommunityReview } from '@ribbit/shared-types';
import { MOCK_SONGS } from '../mocks/songs.mock';
import { MOCK_REVIEWS } from '../mocks/reviews.mock';

@Injectable({ providedIn: 'root' })
export class SongService {
  private readonly songsSignal = signal<readonly Song[]>(MOCK_SONGS);
  private readonly reviewsSignal = signal<readonly CommunityReview[]>(MOCK_REVIEWS);

  readonly songs = this.songsSignal.asReadonly();
  readonly reviews = this.reviewsSignal.asReadonly();

  getSongs(): Observable<readonly Song[]> {
    return of(this.songsSignal()).pipe(
      delay(100),
      tap((songs) => this.songsSignal.set(songs)),
    );
  }

  getReviews(): Observable<readonly CommunityReview[]> {
    return of(this.reviewsSignal()).pipe(
      delay(100),
      tap((reviews) => this.reviewsSignal.set(reviews)),
    );
  }
}
