"""
Setup or reset admin superuser account.

Usage:
    python manage.py setup_admin --email=clif@barge2rail.com --password=xxx

This command will:
1. Find existing user by email, or create new user
2. Set is_staff=True, is_superuser=True
3. Set the provided password
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Setup or reset admin superuser account'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True, help='Admin email address')
        parser.add_argument('--password', required=True, help='Admin password')

    def handle(self, *args, **options):
        User = get_user_model()
        email = options['email']
        password = options['password']

        # Try to find existing user by email or username
        user = User.objects.filter(email=email).first()
        if not user:
            user = User.objects.filter(username=email).first()

        if user:
            self.stdout.write(f"Found existing user: {user.username} ({user.email})")
            user.is_staff = True
            user.is_superuser = True
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Updated user {email} as superuser with new password"))
        else:
            # Create new superuser
            user = User.objects.create_superuser(
                username=email,
                email=email,
                password=password
            )
            self.stdout.write(self.style.SUCCESS(f"Created new superuser: {email}"))

        self.stdout.write(f"\nAdmin URL: https://prt.barge2rail.com/admin/")
        self.stdout.write(f"Login with: {email}")
