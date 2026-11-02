import { Component, ChangeDetectionStrategy, input } from '@angular/core';

@Component({
  selector: 'app-frog',
  standalone: true,
  templateUrl: './frog.component.html',
  styleUrl: './frog.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FrogComponent {
  readonly small = input<boolean>(false);
}
