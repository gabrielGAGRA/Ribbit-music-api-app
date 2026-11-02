import type { Routes } from '@angular/router';
import { DashboardComponent } from './features/dashboard/dashboard.component';
import { DiscoverComponent } from './features/discover/discover.component';
import { ExploreComponent } from './features/explore/explore.component';
import { JamsComponent } from './features/jams/jams.component';
import { NotFoundComponent } from './features/not-found/not-found.component';
import { PlansComponent } from './features/plans/plans.component';
import { PlaylistsComponent } from './features/playlists/playlists.component';
import { CollectionComponent } from './features/profile/collection.component';
import { ProfileComponent } from './features/profile/profile.component';
import { SettingsComponent } from './features/settings/settings.component';

export const routes: Routes = [
  { path: '', redirectTo: 'discover', pathMatch: 'full' },
  { path: 'discover', component: DiscoverComponent, title: 'Ribbit - Descoberta' },
  { path: 'playlists', component: PlaylistsComponent, title: 'Ribbit - Playlists' },
  { path: 'jams', component: JamsComponent, title: 'Ribbit - Jams' },
  { path: 'explore', component: ExploreComponent, title: 'Ribbit - Explorar' },
  { path: 'profile', component: ProfileComponent, title: 'Ribbit - Perfil' },
  { path: 'settings', component: SettingsComponent, title: 'Ribbit - Configurações' },
  { path: 'dashboard', component: DashboardComponent, title: 'Ribbit - Dashboard' },
  {
    path: 'likes',
    component: CollectionComponent,
    data: { kind: 'like' },
    title: 'Ribbit - Músicas Curtidas',
  },
  {
    path: 'loved',
    component: CollectionComponent,
    data: { kind: 'love' },
    title: 'Ribbit - Minhas Amadas',
  },
  {
    path: 'rejected',
    component: CollectionComponent,
    data: { kind: 'reject' },
    title: 'Ribbit - Rejeitadas',
  },
  { path: 'plans', component: PlansComponent, title: 'Ribbit - Planos' },
  { path: '**', component: NotFoundComponent, title: 'Ribbit - Não Encontrado' },
];
