import { Routes } from '@angular/router';
import { Dashboard } from './components/pages/dashboard/dashboard';
import { LoginComponent } from './components/auth/login/login';
import { LayoutMain } from './components/layout/layout-main/layout-main';

export const routes: Routes = [
    {
        path: '',
        component: Dashboard
    },
    {
        path: 'login',
        component: LoginComponent,

    },
    {
        path: '',
        component: LayoutMain,
        children: [
            { path: 'dashboard', component: Dashboard },
            // más rutas internas...
        ]
    },
];
