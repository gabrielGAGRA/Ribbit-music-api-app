import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

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

  protected readonly svgClass = computed<string>(() => {
    const base = this.small() ? 'frog small' : this.size() === 64 ? 'frog size-64' : 'frog';
    const speakingClass = this.speaking() ? ' is-speaking' : '';
    return `${base} mood-${this.mood()}${speakingClass}`;
  });

  protected readonly isMouthOpen = computed<boolean>(
    () => this.speaking() || this.mood() === 'talk' || this.mood() === 'celebrate',
  );
}
