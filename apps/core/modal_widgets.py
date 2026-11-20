from django import forms


class ProfileImageWidget(forms.ClearableFileInput):
    """Keep Django's upload and clear protocol; present only a localized image control."""
    template_name = "widgets/profile_image.html"
