# Configuración de Base de Datos Remota

## Estado Actual ✅

La base de datos ha sido migrada de una configuración local a una **conexión remota simulada**. Esto te permite:

1. **Desarrollar localmente** mientras la BD está fuera del repositorio
2. **Emular una conexión AWS** cambiando solo variables de entorno
3. **Cambiar fácilmente a PostgreSQL** en AWS cuando sea necesario

---

## 📁 Estructura de Archivos

```
proyecto/
├── config/
│   └── settings.py          ← Configuración dinámica de BD
├── .env                     ← Variables de entorno (NO commitear)
├── .env.example             ← Plantilla de configuración
├── migrate_data.py          ← Script para migrar datos
└── db_remote/               ← BD remota (fuera del repo)
    └── referral_platform.db
```

---

## 🔧 Configuración Actual

### Archivo: `.env`

```ini
DATABASE_ENGINE=sqlite
DATABASE_NAME=C:\Users\oscar.jimenez\db_remote\referral_platform.db
```

La BD está ubicada en:
```
C:\Users\oscar.jimenez\db_remote\referral_platform.db
```

### Cambios en `settings.py`

Se añadió lógica para leer la configuración desde variables de entorno:

```python
DATABASE_ENGINE = os.getenv('DATABASE_ENGINE', 'sqlite')

if DATABASE_ENGINE == 'sqlite':
    # Usa SQLite remoto (simulado)
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', ...}}
    
elif DATABASE_ENGINE == 'postgres':
    # Usa PostgreSQL (AWS)
    DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', ...}}
```

---

## 🚀 Uso

### 1. Desarrollo Local (Actual)

```bash
# La aplicación automáticamente usa .env
python manage.py runserver

# Puedes especificar el puerto
python manage.py runserver 0.0.0.0:8000
```

### 2. Migrar a PostgreSQL en AWS

Cuando tengas una VM de AWS con PostgreSQL:

**Paso 1: Edita `.env`**
```ini
DATABASE_ENGINE=postgres
DATABASE_HOST=tu-vm-aws.compute.amazonaws.com
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=tu_contraseña_segura
DATABASE_NAME=referral_platform
```

**Paso 2: Ejecuta migraciones en la nueva BD**
```bash
python manage.py migrate
```

**Paso 3: (Opcional) Migra datos si los tienes**
```bash
python manage.py dumpdata --exclude=sessions --exclude=contenttypes > data.json
# En la BD de AWS:
python manage.py loaddata data.json
```

---

## 📋 Configuración Disponibles

### SQLite (Desarrollo Local)
```ini
DATABASE_ENGINE=sqlite
DATABASE_NAME=/ruta/a/tu/db_remote/referral_platform.db
```

### PostgreSQL (AWS)
```ini
DATABASE_ENGINE=postgres
DATABASE_HOST=your-aws-ip
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=your_password
DATABASE_NAME=referral_platform
```

### PostgreSQL (Desarrollo Local)
```ini
DATABASE_ENGINE=postgres
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=admin
DATABASE_NAME=referral_platform
```

---

## 🔐 Seguridad

⚠️ **Importante**: El archivo `.env` NO debe ser commiteado

```bash
# Verifica que esté en .gitignore
cat .gitignore
```

Debe contener:
```
.env
.env.local
*.db
```

---

## 🛠️ Scripts Útiles

### Crear backup de la BD
```bash
python manage.py dumpdata > backup.json
```

### Restaurar desde backup
```bash
python manage.py loaddata backup.json
```

### Ver estado de migraciones
```bash
python manage.py showmigrations
```

### Ejecutar una migración específica
```bash
python manage.py migrate referrals 0002
```

---

## 📊 Verificar Conexión

```bash
# Abre la shell de Django
python manage.py shell

# Dentro de la shell:
from django.conf import settings
from django.db import connection

print(settings.DATABASES['default'])
print("Conexión OK!" if connection.connection else "Error de conexión")
```

---

## 🐛 Troubleshooting

### Error: "No module named 'dotenv'"
```bash
pip install python-dotenv
```

### Error: "database is locked" (SQLite)
Cierra todas las instancias de la aplicación y intenta de nuevo.

### Error: "connection refused" (PostgreSQL)
- Verifica que PostgreSQL esté corriendo
- Comprueba la IP y puerto en `.env`
- Verifica credenciales de usuario

### Error: "No such file or directory" (SQLite)
Asegúrate de que la carpeta `db_remote` existe:
```bash
mkdir C:\Users\oscar.jimenez\db_remote
```

---

## ✨ Próximos Pasos

1. **Prueba la conexión actual**:
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

2. **Cuando estés listo para AWS**:
   - Configura una VM con PostgreSQL
   - Actualiza `.env`
   - Ejecuta migraciones en la nueva BD

3. **Considera backup automático**:
   - Cron job (Linux/Mac) o Task Scheduler (Windows)
   - Cloud storage (S3, Azure Blob, etc)

---

## 📚 Referencias

- [Django Database Documentation](https://docs.djangoproject.com/en/6.0/ref/settings/#databases)
- [Python dotenv](https://github.com/theskumar/python-dotenv)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [AWS RDS for PostgreSQL](https://aws.amazon.com/rds/postgresql/)
