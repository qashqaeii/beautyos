from django.contrib.auth.base_user import BaseUserManager

from apps.core.utils.phone import normalize_iran_mobile


class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra_fields):
        phone = normalize_iran_mobile(phone)
        user = self.model(phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        if not password:
            raise ValueError("Superuser requires a password.")
        return self.create_user(phone, password, **extra_fields)
