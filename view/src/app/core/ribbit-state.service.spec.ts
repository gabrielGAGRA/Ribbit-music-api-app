import { describe, it, expect, beforeEach } from 'vitest';
import { RibbitStateService } from './ribbit-state.service';

describe('RibbitStateService', () => {
  let service: RibbitStateService;

  beforeEach(() => {
    localStorage.clear();
    service = new RibbitStateService();
  });

  it('should initialize with default songs and user name', () => {
    expect(service.songs().length).toBeGreaterThan(0);
    expect(service.userName()).toBe('João Lucas');
    expect(service.currentPlan()).toBe('Free');
  });

  it('should record a like decision and advance to next available song', () => {
    const initialIndex = service.currentIndex();
    service.decide('like');

    expect(service.history().length).toBe(1);
    expect(service.history()[0].kind).toBe('like');
    expect(service.history()[0].index).toBe(initialIndex);
    expect(service.currentIndex()).toBeGreaterThan(initialIndex);
  });

  it('should record a love decision and update toast', () => {
    service.decide('love');
    expect(service.history()[0].kind).toBe('love');
    expect(service.toast()).toContain('favorita');
  });

  it('should allow undoing the last decision', () => {
    const initialIndex = service.currentIndex();
    service.decide('reject');
    expect(service.history().length).toBe(1);

    service.undo();
    expect(service.history().length).toBe(0);
    expect(service.currentIndex()).toBe(initialIndex);
    expect(service.toast()).toContain('desfeito');
  });

  it('should create new playlists and add songs to existing playlists', () => {
    const initialCount = service.playlists().length;
    service.createPlaylist('Nova Playlist', 45);

    expect(service.playlists().length).toBe(initialCount + 1);
    expect(service.playlists().some((p) => p.name === 'Nova Playlist')).toBe(true);

    service.addSongToPlaylist(0);
    expect(service.playlists()[0].count).toBeGreaterThan(0);
  });

  it('should manage temporary queue decisions', () => {
    expect(service.queue().length).toBe(0);
    service.decideQueue(true);
    expect(service.queue().length).toBe(1);

    service.decideQueue(false);
    expect(service.queue().length).toBe(1);
  });

  it('should handle jam votes and threshold', () => {
    expect(service.jamVotes()).toBe(0);
    service.voteSkipJam();
    expect(service.jamVotes()).toBe(1);
    expect(service.toast()).toContain('voto');
  });

  it('should allow updating user plan and account deletion', () => {
    service.setPlan('Individual');
    expect(service.currentPlan()).toBe('Individual');

    service.deleteAccount();
    expect(service.history().length).toBe(0);
    expect(service.playlists().length).toBe(0);
    expect(service.authView()).toBe('register');
  });
});
