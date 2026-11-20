from django.contrib.staticfiles import finders
import pytest


@pytest.mark.django_db
def test_runtime_assets_are_local(client):
    response = client.get("/")
    assert response.status_code == 200
    content = response.content.decode()
    for path in ("css/local-fonts.css", "js/vendor/alpine-3.14.8.min.js", "js/vendor/htmx-2.0.4.min.js"):
        assert path in content
        assert finders.find(path)
    for path in ("fonts/vazirmatn.woff2", "fonts/markazi-text.ttf"):
        assert finders.find(path)
    assert "fonts.bunny.net" not in content
    assert "unpkg.com" not in content
