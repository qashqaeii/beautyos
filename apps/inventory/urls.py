from django.urls import path

from apps.inventory import views

app_name = "inventory"

urlpatterns = [
    path("", views.list_items, name="list"),
    path("new/", views.item_create, name="create"),
    path("categories/", views.categories_manage, name="categories"),
    path("<int:pk>/in/", views.stock_in, name="stock_in"),
    path("<int:pk>/out/", views.stock_out, name="stock_out"),
]
