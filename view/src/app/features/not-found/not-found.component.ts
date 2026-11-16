import { Component, ChangeDetectionStrategy } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FrogComponent } from '../../shared/frog.component';
import { IconComponent } from '../../shared/icon.component';

@Component({
  selector: 'app-not-found',
  standalone: true,
  imports: [RouterLink, FrogComponent, IconComponent],
  templateUrl: './not-found.component.html',
  styleUrl: './not-found.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NotFoundComponent {}
