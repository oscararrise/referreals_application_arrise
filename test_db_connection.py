#!/usr/bin/env python
"""
Script para verificar que la conexión a la BD remota funciona correctamente
"""

import os
import sys
from pathlib import Path

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.conf import settings
from django.db import connection, connections
from django.db.utils import OperationalError


def test_database_connection():
    """Prueba la conexión a la base de datos"""
    
    print("\n" + "="*70)
    print("PRUEBA DE CONEXIÓN - BASE DE DATOS REMOTA")
    print("="*70)
    
    try:
        # 1. Mostrar configuración
        db_config = settings.DATABASES['default']
        print("\n📋 CONFIGURACIÓN:")
        print(f"   Engine: {db_config['ENGINE']}")
        print(f"   Name:   {db_config['NAME']}")
        
        if 'HOST' in db_config:
            print(f"   Host:   {db_config['HOST']}")
        if 'PORT' in db_config:
            print(f"   Port:   {db_config['PORT']}")
        
        # 2. Probar conexión
        print("\n🔗 PROBANDO CONEXIÓN...")
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
        
        print("   ✅ Conexión exitosa")
        
        # 3. Obtener información de la BD
        print("\n📊 INFORMACIÓN DE LA BD:")
        
        from django.apps import apps
        from users.models import CustomUser
        
        total_users = CustomUser.objects.count()
        print(f"   Usuarios: {total_users}")
        
        # Contar modelos
        models_count = 0
        for model in apps.get_models():
            if model._meta.app_label not in ['contenttypes', 'sessions']:
                count = model.objects.count()
                models_count += 1
                if count > 0:
                    print(f"   {model._meta.verbose_name_plural}: {count}")
        
        print(f"\n   Total de modelos: {models_count}")
        
        # 4. Verificar archivo de BD
        print("\n💾 ARCHIVO DE BD:")
        db_path = Path(db_config['NAME'])
        if db_path.exists():
            size_kb = db_path.stat().st_size / 1024
            print(f"   ✅ Archivo existe: {db_path}")
            print(f"   Tamaño: {size_kb:.2f} KB")
        else:
            print(f"   ⚠️  Archivo no encontrado: {db_path}")
        
        # 5. Resumen
        print("\n" + "="*70)
        print("✅ TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE")
        print("="*70)
        
        print("\n🚀 PRÓXIMOS PASOS:")
        print("   1. Ejecuta: python manage.py runserver")
        print("   2. Accede a: http://localhost:8000")
        print("   3. Panel de administrador: http://localhost:8000/admin")
        
        print("\n🔄 CAMBIAR A POSTGRESQL EN AWS:")
        print("   1. Edita el archivo .env")
        print("   2. Cambia DATABASE_ENGINE=postgres")
        print("   3. Actualiza DATABASE_HOST, PORT, USER, PASSWORD")
        print("   4. Ejecuta: python manage.py migrate")
        
        return True
        
    except OperationalError as e:
        print(f"\n❌ ERROR DE CONEXIÓN: {e}")
        print("\nVerifica:")
        print(f"   - La carpeta de BD existe: C:\\Users\\oscar.jimenez\\db_remote")
        print(f"   - El archivo tiene permisos de lectura/escritura")
        print(f"   - PostgreSQL está corriendo (si usas postgres)")
        return False
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_database_connection()
    sys.exit(0 if success else 1)
