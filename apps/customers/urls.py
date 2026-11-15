from django.urls import path

from apps.customers import views

app_name = "customers"

urlpatterns = [
    path("", views.customer_list, name="list"),
    path("search/", views.customer_search, name="search"),
    path("new/", views.customer_create, name="create"),
    path("<int:pk>/", views.customer_detail, name="detail"),
    path("<int:pk>/edit/", views.customer_edit, name="edit"),
    path("<int:pk>/notes/", views.customer_add_note, name="add_note"),
    path("<int:pk>/archive/", views.customer_archive, name="archive"),
]
