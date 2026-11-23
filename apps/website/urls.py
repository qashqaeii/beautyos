from django.urls import path

from apps.website import views

app_name = "website"

urlpatterns = [
    path("", views.home, name="home"),
    path("features/", views.features, name="features"),
    path("blog/", views.blog_index, name="blog"),
    # str also accepts validated Persian slugs; slug converter is ASCII-only.
    path("blog/<str:slug>/", views.blog_post, name="blog_post"),
    path("contact/", views.contact, name="contact"),
    path("faq/", views.faq, name="faq"),
    path("privacy/", views.privacy, name="privacy"),
    path("terms/", views.terms, name="terms"),
]