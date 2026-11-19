import pytest


@pytest.mark.django_db
def test_mobile_account_menu_and_safe_logout(client, owner_membership):
    client.force_login(owner_membership.user)
    response = client.get("/app/")
    assert response.status_code == 200
    html = response.content.decode()
    assert "css/luna-responsive.css" in html
    assert 'id="mobile-account-sheet"' in html
    assert 'aria-controls="mobile-account-sheet"' in html
    assert "خروج از حساب" in html
    assert 'method="post"' in html


@pytest.mark.django_db
def test_custom_workspace_headers_do_not_render_empty_shell_header(client, owner_membership):
    from django.urls import reverse

    client.force_login(owner_membership.user)
    for url in ("/app/", reverse("dashboard:management"), reverse("customers:list"), reverse("staff:list")):
        response = client.get(url)
        assert response.status_code == 200
        html = response.content.decode()
        assert 'class="maison-unified-header ' not in html
        assert 'class="luna-sidebar-toggle"' in html
        assert html.count("<h1") == 1
