import { Routes } from '@angular/router';
import { Dashboard } from './components/pages/dashboard/dashboard';
import { LoginComponent } from './components/auth/login/login';
import { LayoutMain } from './components/layout/layout-main/layout-main';
import { UserList } from './modules/users/list/user-list';

export const routes: Routes = [
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
            { path: 'usuarios', component: UserList }
        ]
    },
];
