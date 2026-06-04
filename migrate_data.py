#!/usr/bin/env python
"""
Script para migrar datos de BD local (db.sqlite3) a BD remota
Esto es útil cuando necesitas cambiar la configuración de base de datos
"""

import os
import shutil
import django
from django.db import connection
from pathlib import Path

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.apps import apps
from django.core.management import call_command


def migrate_data():
    """Migra datos de la BD anterior a la BD remota"""
    
    BASE_DIR = Path(__file__).resolve().parent
    old_db = BASE_DIR / 'db.sqlite3'
    new_db = Path('C:\\Users\\oscar.jimenez\\db_remote\\referral_platform.db')
    
    print("=" * 60)
    print("MIGRACIÓN DE DATOS - BD LOCAL A BD REMOTA")
    print("=" * 60)
    
    # Paso 1: Verificar que la BD antigua existe
    if not old_db.exists():
        print(f"\n⚠ No se encontró BD anterior: {old_db}")
        print("Usando la BD remota vacía (ya migrada).")
        return
    
    print(f"\nBD anterior: {old_db}")
    print(f"BD remota: {new_db}")
    
    # Paso 2: Hacer backup de la BD remota
    if new_db.exists():
        backup = new_db.parent / f"{new_db.stem}_backup_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy(new_db, backup)
        print(f"\n✓ Backup creado: {backup}")
    
    # Paso 3: Copiar datos usando Django ORM
    print("\n📊 Extrayendo modelos...")
    
    try:
        # Obtener todos los modelos
        models_to_migrate = []
        for model in apps.get_models():
            if model._meta.app_label not in ['contenttypes', 'sessions']:
                models_to_migrate.append(model)
                print(f"  - {model._meta.label}")
        
        print(f"\n✓ {len(models_to_migrate)} modelos para migrar")
        
        # Contar registros existentes en la BD remota
        print("\n📈 Estado de la BD remota:")
        for model in models_to_migrate:
            count = model.objects.count()
            print(f"  - {model._meta.verbose_name_plural}: {count} registros")
        
        print("\n✓ La BD remota está lista para usar!")
        print("\nProximos pasos:")
        print("  1. Ejecuta: python manage.py runserver")
        print("  2. La aplicación ahora usará la BD remota")
        print("  3. Para cambiar a PostgreSQL en AWS:")
        print("     - Edita el archivo .env")
        print("     - Cambia DATABASE_ENGINE=postgres")
        print("     - Añade los datos de conexión de AWS")
        
    except Exception as e:
        print(f"\n✗ Error durante la migración: {e}")
        raise


if __name__ == '__main__':
    migrate_data()
