import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RibbitStateService } from '../core/ribbit-state.service';
import { FrogComponent } from './frog.component';
import { IconComponent } from './icon.component';

/** Floating non-blocking Ribby speech bubble surfacing restrictions and actionable guidance. */
@Component({
  selector: 'app-ribby-alert',
  standalone: true,
  imports: [FrogComponent, IconComponent],
  templateUrl: './ribby-alert.component.html',
  styleUrl: './ribby-alert.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RibbyAlertComponent {
  protected readonly state = inject(RibbitStateService);

  protected dismissAlert(event?: Event): void {
    event?.stopPropagation();
    this.state.dismissRibbyAlert();
  }

  protected pauseAutoDismiss(): void {
    this.state.pauseRibbyAlert();
  }

  protected resumeAutoDismiss(): void {
    this.state.resumeRibbyAlert();
  }
}
