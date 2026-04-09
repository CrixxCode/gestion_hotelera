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
import { HotelSettings } from './components/pages/hotel-settings/hotel-settings';
import { MasterDataComponent } from './components/pages/master-data/master-data';

const loadClientsComponent = () => import('./modules/clients/list-clients/list-clients').then((m) => m.ListClients);
const loadReservationsComponent = () =>
  import('./modules/reservations/list-reservations/list-reservations').then((m) => m.ListReservations);
const loadRoomsComponent = () => import('./modules/rooms/list-rooms/list-rooms').then((m) => m.ListRooms);
const loadRoomTypesComponent = () =>
  import('./modules/rooms/list-room-types/list-room-types').then((m) => m.ListRoomTypes);
const loadRatesComponent = () => import('./modules/rooms/list-rates/list-rates').then((m) => m.ListRates);
const loadAmenitiesComponent = () => import('./modules/rooms/amenities/amenities').then((m) => m.AmenitiesPage);
const loadServicesComponent = () =>
  import('./modules/services/list-services/list-services').then((m) => m.ListServices);
const loadBillingComponent = () => import('./modules/billing/list-bill/list-bill').then((m) => m.ListBill);
const loadPaymentsComponent = () =>
  import('./modules/payments/list-payments/list-payments').then((m) => m.ListPayments);
const loadIncomeConsolidatedComponent = () =>
  import('./modules/income-consolidated/list-income-consolidated/list-income-consolidated').then(
    (m) => m.ListIncomeConsolidated
  );
const loadFinancialControlComponent = () =>
  import('./modules/financial-control/list-financial-control/list-financial-control').then(
    (m) => m.ListFinancialControl
  );
const loadExpensesComponent = () =>
  import('./modules/expenses/list-expenses/list-expenses').then((m) => m.ListExpenses);
const loadPackagesComponent = () =>
  import('./modules/packages/list-packages/list-packages').then((m) => m.ListPackages);
const loadPromotionsComponent = () =>
  import('./modules/promotions/list-promotions/list-promotions').then((m) => m.ListPromotions);
const loadItemsComponent = () => import('./modules/items/list-items/list-items').then((m) => m.ListItems);
const loadRoomInventoryComponent = () =>
  import('./modules/room-inventory/list-room-inventory/list-room-inventory').then((m) => m.ListRoomInventory);
const loadInventoryMovementsComponent = () =>
  import('./modules/inventory-movements/list-inventory-movements/list-inventory-movements').then(
    (m) => m.ListInventoryMovements
  );
const loadCleaningTasksComponent = () =>
  import('./modules/cleaning-tasks/list-cleaning-tasks/list-cleaning-tasks').then((m) => m.ListCleaningTasks);
const loadMaintenanceOrdersComponent = () =>
  import('./modules/maintenance-orders/list-maintenance-orders/list-maintenance-orders').then(
    (m) => m.ListMaintenanceOrders
  );
const loadReportsComponent = () =>
  import('./modules/reports/list-reports/list-reports').then((m) => m.ListReports);

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
            { path: 'clientes', loadComponent: loadClientsComponent },
            { path: 'reservas', loadComponent: loadReservationsComponent },
            { path: 'habitaciones', loadComponent: loadRoomsComponent },
            { path: 'tipos-habitacion', loadComponent: loadRoomTypesComponent },
            { path: 'room-types', redirectTo: 'tipos-habitacion', pathMatch: 'full' },
            { path: 'tarifas-habitacion', loadComponent: loadRatesComponent },
            { path: 'tarifas', redirectTo: 'tarifas-habitacion', pathMatch: 'full' },
            { path: 'rates', redirectTo: 'tarifas-habitacion', pathMatch: 'full' },
            { path: 'amenidades', loadComponent: loadAmenitiesComponent },
            { path: 'amenities', redirectTo: 'amenidades', pathMatch: 'full' },
            { path: 'servicios-consumos', loadComponent: loadServicesComponent },
            { path: 'servicios', redirectTo: 'servicios-consumos', pathMatch: 'full' },
            { path: 'services', redirectTo: 'servicios-consumos', pathMatch: 'full' },
            { path: 'facturacion', loadComponent: loadBillingComponent },
            { path: 'facturas', redirectTo: 'facturacion', pathMatch: 'full' },
            { path: 'billing', redirectTo: 'facturacion', pathMatch: 'full' },
            { path: 'pagos', loadComponent: loadPaymentsComponent },
            { path: 'payments', redirectTo: 'pagos', pathMatch: 'full' },
            { path: 'consolidado-ingresos', loadComponent: loadIncomeConsolidatedComponent },
            { path: 'control-financiero', loadComponent: loadFinancialControlComponent },
            { path: 'financial-control', redirectTo: 'control-financiero', pathMatch: 'full' },
            { path: 'ingresos', redirectTo: 'consolidado-ingresos', pathMatch: 'full' },
            { path: 'income-consolidated', redirectTo: 'consolidado-ingresos', pathMatch: 'full' },
            { path: 'egresos', loadComponent: loadExpensesComponent },
            { path: 'expenses', redirectTo: 'egresos', pathMatch: 'full' },
            { path: 'catalogo-paquetes', loadComponent: loadPackagesComponent },
            { path: 'paquetes', redirectTo: 'catalogo-paquetes', pathMatch: 'full' },
            { path: 'packages', redirectTo: 'catalogo-paquetes', pathMatch: 'full' },
            { path: 'promociones', loadComponent: loadPromotionsComponent },
            { path: 'promotions', redirectTo: 'promociones', pathMatch: 'full' },
            { path: 'items', loadComponent: loadItemsComponent },
            { path: 'inventario-items', redirectTo: 'items', pathMatch: 'full' },
            { path: 'inventory-items', redirectTo: 'items', pathMatch: 'full' },
            { path: 'inventario-habitaciones', loadComponent: loadRoomInventoryComponent },
            { path: 'room-inventory', redirectTo: 'inventario-habitaciones', pathMatch: 'full' },
            { path: 'movimientos-inventario', loadComponent: loadInventoryMovementsComponent },
            { path: 'inventory-movements', redirectTo: 'movimientos-inventario', pathMatch: 'full' },
            { path: 'tareas-limpieza', loadComponent: loadCleaningTasksComponent },
            { path: 'cleaning-tasks', redirectTo: 'tareas-limpieza', pathMatch: 'full' },
            { path: 'ordenes-mantenimiento', loadComponent: loadMaintenanceOrdersComponent },
            { path: 'maintenance-orders', redirectTo: 'ordenes-mantenimiento', pathMatch: 'full' },
            { path: 'reportes', loadComponent: loadReportsComponent },
            { path: 'reports', redirectTo: 'reportes', pathMatch: 'full' },
            { path: 'hotel-config', component: HotelSettings },
            { path: 'master-data', component: MasterDataComponent },
        ]
    },
];

