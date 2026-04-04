import { Routes } from '@angular/router';
import { Dashboard } from './components/pages/dashboard/dashboard';
import { LoginComponent } from './components/auth/login/login';
import { ForgotPasswordComponent } from './components/auth/forgot-password/forgot-password';
import { ResetPasswordComponent } from './components/auth/reset-password/reset-password';
import { LayoutMain } from './components/layout/layout-main/layout-main';
import { UserList } from './modules/users/list/user-list';
import { UserRegister } from './modules/users/register/register';
import { RolesComponent } from './components/pages/roles/roles';
import { RecursosComponent } from './components/pages/recursos/recursos';
import { ListClients } from './modules/clients/list-clients/list-clients';
import { HotelSettings } from './components/pages/hotel-settings/hotel-settings';
import { MasterDataComponent } from './components/pages/master-data/master-data';
import { ListRooms } from './modules/rooms/list-rooms/list-rooms';
import { AmenitiesPage } from './modules/rooms/amenities/amenities';
import { ListReservations } from './modules/reservations/list-reservations/list-reservations';
import { ListServices } from './modules/services/list-services/list-services';
import { ListPackages } from './modules/packages/list-packages/list-packages';

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
            { path: 'usuarios', component: UserList },
            { path: 'dashboard', component: Dashboard },
            { path: 'roles', component: RolesComponent },
            { path: 'recursos', component: RecursosComponent },
            { path: 'clientes', component: ListClients },
            { path: 'reservas', component: ListReservations },
            { path: 'habitaciones', component: ListRooms },
            { path: 'amenidades', component: AmenitiesPage },
            { path: 'amenities', component: AmenitiesPage },
            { path: 'servicios-consumos', component: ListServices },
            { path: 'servicios', component: ListServices },
            { path: 'services', component: ListServices },
            { path: 'catalogo-paquetes', component: ListPackages },
            { path: 'paquetes', component: ListPackages },
            { path: 'packages', component: ListPackages },
            { path: 'hotel-config', component: HotelSettings },
            { path: 'master-data', component: MasterDataComponent },
        ]
    },
];

