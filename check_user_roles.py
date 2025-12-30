#!/usr/bin/env python
"""
Quick script to check and assign roles to a user
Run: python check_user_roles.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, '/Users/hardiksottany/PycharmProjects/license-manager/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
django.setup()

from accounts.models import User, Role

def check_user(username):
    """Check user's roles and permissions"""
    try:
        user = User.objects.get(username=username)
        print(f"\n{'='*60}")
        print(f"User: {username}")
        print(f"{'='*60}")
        print(f"ID: {user.id}")
        print(f"Email: {user.email}")
        print(f"Is Active: {user.is_active}")
        print(f"Is Superuser: {user.is_superuser}")
        print(f"\nAssigned Roles:")

        if user.is_superuser:
            print("  → SUPERUSER (Has all permissions automatically)")

        roles = user.roles.all()
        if roles:
            for role in roles:
                print(f"  - {role.name} ({role.code})")
        else:
            print("  → No roles assigned!")

        print(f"\nRole Codes: {user.get_role_codes()}")
        print(f"{'='*60}\n")

        return user
    except User.DoesNotExist:
        print(f"❌ User '{username}' not found!")
        return None

def assign_all_roles(username):
    """Assign all active roles to a user"""
    try:
        user = User.objects.get(username=username)
        all_roles = Role.objects.filter(is_active=True)
        user.roles.set(all_roles)
        print(f"✅ Assigned {all_roles.count()} roles to {username}")
        return True
    except User.DoesNotExist:
        print(f"❌ User '{username}' not found!")
        return False

def assign_viewer_roles(username):
    """Assign all viewer roles to a user"""
    try:
        user = User.objects.get(username=username)
        viewer_roles = Role.objects.filter(
            code__icontains='VIEWER',
            is_active=True
        )
        user.roles.set(viewer_roles)
        print(f"✅ Assigned {viewer_roles.count()} viewer roles to {username}")
        for role in viewer_roles:
            print(f"  - {role.name}")
        return True
    except User.DoesNotExist:
        print(f"❌ User '{username}' not found!")
        return False

def assign_manager_roles(username):
    """Assign all manager roles to a user"""
    try:
        user = User.objects.get(username=username)
        manager_roles = Role.objects.filter(
            code__icontains='MANAGER',
            is_active=True
        )
        user.roles.set(manager_roles)
        print(f"✅ Assigned {manager_roles.count()} manager roles to {username}")
        for role in manager_roles:
            print(f"  - {role.name}")
        return True
    except User.DoesNotExist:
        print(f"❌ User '{username}' not found!")
        return False

def list_all_roles():
    """List all available roles"""
    print(f"\n{'='*60}")
    print("Available Roles")
    print(f"{'='*60}")
    roles = Role.objects.filter(is_active=True).order_by('name')
    for i, role in enumerate(roles, 1):
        print(f"{i:2d}. {role.name:30s} ({role.code})")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    print("\n🔍 User Role Management Tool\n")

    # Check jaymota user
    username = "jaymota"
    user = check_user(username)

    if user:
        list_all_roles()

        print("\nOptions:")
        print("1. Assign ALL roles")
        print("2. Assign VIEWER roles only")
        print("3. Assign MANAGER roles only")
        print("4. Check another user")
        print("5. Exit")

        choice = input("\nEnter choice (1-5): ").strip()

        if choice == "1":
            assign_all_roles(username)
            check_user(username)
        elif choice == "2":
            assign_viewer_roles(username)
            check_user(username)
        elif choice == "3":
            assign_manager_roles(username)
            check_user(username)
        elif choice == "4":
            new_username = input("Enter username: ").strip()
            check_user(new_username)

        print("\n✅ Done! User needs to log out and log in again for changes to take effect.\n")
