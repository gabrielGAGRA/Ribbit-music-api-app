import { Component, ChangeDetectionStrategy, input } from '@angular/core';
import { IconName } from '@ribbit/shared-types';

@Component({
  selector: 'app-icon',
  standalone: true,
  templateUrl: './icon.component.html',
  styleUrl: './icon.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class IconComponent {
  readonly name = input.required<IconName>();
  readonly size = input<number>(20);
  readonly className = input<string>('');
}
