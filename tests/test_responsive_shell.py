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
