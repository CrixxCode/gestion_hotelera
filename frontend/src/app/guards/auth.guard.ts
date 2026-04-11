import { inject } from '@angular/core';
import { CanActivateFn, CanActivateChildFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { MessageService } from 'primeng/api';
import { AuthService } from '../services/auth/auth';

const buildLoginRedirect = (router: Router, targetUrl: string) => {
  const returnUrl =
    targetUrl && targetUrl !== '/login' && targetUrl !== '/'
      ? { returnUrl: targetUrl }
      : undefined;
  return router.createUrlTree(['/login'], { queryParams: returnUrl });
};

const showAuthRequiredToast = (messageService: MessageService) => {
  messageService.add({
    key: 'auth',
    severity: 'warn',
    summary: 'Sesion requerida',
    detail: 'Debes iniciar sesion para continuar.',
    life: 3000,
  });
};

const validateSession = (targetUrl: string) => {
  const authService = inject(AuthService);
  const router = inject(Router);
  const messageService = inject(MessageService);

  return authService.checkSession().pipe(
    map((isAuthenticated) => {
      if (isAuthenticated) {
        return true;
      }
      showAuthRequiredToast(messageService);
      return buildLoginRedirect(router, targetUrl);
    }),
    catchError(() => {
      showAuthRequiredToast(messageService);
      return of(buildLoginRedirect(router, targetUrl));
    })
  );
};

export const authGuard: CanActivateFn = (_route, state) => validateSession(state.url);

export const authChildGuard: CanActivateChildFn = (_route, state) => validateSession(state.url);
