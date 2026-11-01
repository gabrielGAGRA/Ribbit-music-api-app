import { Component, ChangeDetectionStrategy, inject } from '@angular/core';
import { RibbitStateService } from '../core/ribbit-state.service';
import { IconComponent } from './icon.component';

@Component({
  selector: 'app-toast',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './toast.component.html',
  styleUrl: './toast.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ToastComponent {
  protected readonly state = inject(RibbitStateService);

  protected closeToast(): void {
    this.state.clearToast();
  }
}
