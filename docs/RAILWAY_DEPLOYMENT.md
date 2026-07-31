# Despliegue en Railway

Este proyecto se despliega como un solo servicio Docker:

- Angular se compila en el build de Docker.
- Django sirve el API y el `index.html` del frontend.
- PostgreSQL se conecta con las variables `PG*` que Railway expone desde el servicio de base de datos.

## Pasos en Railway

1. Sube estos cambios a GitHub.
2. En Railway, crea un proyecto nuevo desde el repositorio.
3. Agrega un servicio PostgreSQL al mismo proyecto.
4. En el servicio web, confirma que Railway detecte el `Dockerfile` del repositorio.
5. Genera un dominio publico en `Settings > Networking > Public Networking > Generate Domain`.
6. Configura estas variables en el servicio web:

```env
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=replace-with-a-long-random-secret
DB_ENGINE=postgres
DB_NAME=${{Postgres.PGDATABASE}}
DB_USER=${{Postgres.PGUSER}}
DB_PASSWORD=${{Postgres.PGPASSWORD}}
DB_HOST=${{Postgres.PGHOST}}
DB_PORT=${{Postgres.PGPORT}}
```

Si Railway no inyecta `RAILWAY_PUBLIC_DOMAIN` en tu servicio, agrega tambien:

```env
DJANGO_ALLOWED_HOSTS=tu-dominio.up.railway.app
CORS_ALLOWED_ORIGINS=https://tu-dominio.up.railway.app
CSRF_TRUSTED_ORIGINS=https://tu-dominio.up.railway.app
```

## CLI opcional

Si prefieres desplegar desde terminal:

```powershell
npm install -g @railway/cli
railway login
railway init
railway up
```

El servicio ejecuta migraciones y `collectstatic` al arrancar.

## Notas

- Los archivos en `backend/media` no son persistentes en Railway sin un Volume o almacenamiento externo.
- El primer despliegue puede tardar por la instalacion de dependencias de Node y Python.
