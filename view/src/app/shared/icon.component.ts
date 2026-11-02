import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import type { IconName } from '@ribbit/shared-types';

/** Renders Ribbit SVG stroke icons by semantic icon name. */
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
