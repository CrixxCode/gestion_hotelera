import { Routes } from '@angular/router';
import { Dashboard } from './components/pages/dashboard/dashboard';
import { LoginComponent } from './components/auth/login/login';
import { ForgotPasswordComponent } from './components/auth/forgot-password/forgot-password';
import { ResetPasswordComponent } from './components/auth/reset-password/reset-password';
import { LayoutMain } from './components/layout/layout-main/layout-main';
import { UserList } from './modules/users/list/user-list';
import { UserRegister } from './modules/users/register/register';

export const routes: Routes = [
    {
        path: '',
        component: LoginComponent,

    },
    {
        path: 'login',
        component: LoginComponent,

    },
    {
        path: 'forgot-password',
        component: ForgotPasswordComponent,
    },
    {
        path: 'reset-password',
        component: ResetPasswordComponent,
    },
    {
        path: '',
        component: LayoutMain,
        children: [
            { path: 'dashboard', component: Dashboard },
            // más rutas internas...
            { path: 'usuarios', component: UserList },
        ]
    },
    // {
    //     path: '**',
    //     component: LoginComponent
    // }
];
