import '@angular/compiler';
import { getTestBed } from '@angular/core/testing';
import { BrowserTestingModule, platformBrowserTesting } from '@angular/platform-browser/testing';
import { afterEach } from 'vitest';

getTestBed().initTestEnvironment(BrowserTestingModule, platformBrowserTesting());

afterEach(() => {
  getTestBed().resetTestingModule();
});

if (typeof HTMLMediaElement !== 'undefined') {
  HTMLMediaElement.prototype.play = () =>
    Promise.reject(new Error('Media playback unavailable in JSDOM'));
  HTMLMediaElement.prototype.pause = () => {};
}
