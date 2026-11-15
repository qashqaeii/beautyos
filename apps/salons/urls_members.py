from django.urls import path

from apps.salons import views_members

app_name = "salons_members"

urlpatterns = [
    path("", views_members.members_home, name="home"),
    path("invite/", views_members.invite_create, name="invite"),
    path("invite/<int:pk>/cancel/", views_members.invite_cancel, name="invite_cancel"),
    path("<int:pk>/toggle-staff-manage/", views_members.toggle_staff_manage, name="toggle_staff_manage"),
    path("accept/<str:token>/", views_members.accept_invite, name="accept"),
]
