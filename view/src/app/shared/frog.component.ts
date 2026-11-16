import { Component, ChangeDetectionStrategy, input } from '@angular/core';

export type FrogMood = 'idle' | 'wave' | 'talk' | 'excited' | 'celebrate';

@Component({
  selector: 'app-frog',
  standalone: true,
  templateUrl: './frog.component.html',
  styleUrl: './frog.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FrogComponent {
  readonly small = input<boolean>(false);
  readonly size = input<number | undefined>(undefined);
  readonly mood = input<FrogMood>('idle');
  readonly speaking = input<boolean>(false);
}
