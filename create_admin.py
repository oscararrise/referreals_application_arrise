import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from users.models import CustomUser

print("\n" + "="*60)
print("CREAR USUARIO ADMIN EN BD REMOTA")
print("="*60)

# Verificar si ya existe
if CustomUser.objects.filter(username='admin').exists():
    print("\n✓ El usuario 'admin' ya existe")
    user = CustomUser.objects.get(username='admin')
    print(f"  Email: {user.email}")
    print(f"  Staff: {user.is_staff}")
    print(f"  Superuser: {user.is_superuser}")
else:
    print("\n📝 Creando usuario 'admin'...")
    user = CustomUser.objects.create_superuser(
        username='admin',
        email='admin@arrise.com',
        password='admin123'
    )
    print("\n✅ USUARIO CREADO EXITOSAMENTE")
    print(f"  Usuario: {user.username}")
    print(f"  Email: {user.email}")
    print(f"  Contraseña: admin123")
    print(f"  Permisos: Admin/Superuser")

print("\n" + "="*60)
print("CREDENCIALES DE ACCESO")
print("="*60)
print("\n  URL: http://localhost:8000/admin")
print("  Usuario: admin")
print("  Contraseña: admin123")
print("\n" + "="*60)
