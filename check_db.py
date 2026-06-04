import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from users.models import CustomUser
from django.contrib.auth.models import Group, Permission

print("\n👥 USUARIOS EXISTENTES:")
users = CustomUser.objects.all()
if users.exists():
    for user in users:
        print(f"   - {user.username} ({user.email})")
        print(f"     Staff: {user.is_staff}, Superuser: {user.is_superuser}")
else:
    print("   ✗ No hay usuarios")

print("\n🔐 GRUPOS:")
groups = Group.objects.all()
if groups.exists():
    for group in groups:
        print(f"   - {group.name}")
else:
    print("   ✗ No hay grupos")

print("\n📝 PERMISOS:")
perms = Permission.objects.count()
print(f"   Total: {perms} permisos")
