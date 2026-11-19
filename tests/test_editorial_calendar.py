from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from html.parser import HTMLParser

import pytest
from django.urls import reverse
from django.utils import timezone
from apps.core.utils.dates import to_jalali


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = []
        self.booking = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag != "a":
            return
        classes = attrs.get("class", "").split()
        if "appt-month-card__day" in classes:
            self.days.append(attrs["href"])
        if "appt-month-day-list__book" in classes:
            self.booking.append(attrs["href"])


@pytest.mark.django_db
def test_editorial_calendar_empty_assets_and_unique_day_query(client, owner_membership):
    client.force_login(owner_membership.user)
    today = timezone.localdate()
    response = client.get(reverse("appointments:calendar"), {"day": today.isoformat()})
    assert response.status_code == 200
    html = response.content.decode()
    assert "editorial-calendar-shell" in html
    assert "editorial-calendar.css" in html
    assert "editorial-calendar-empty-card" in html
    assert "images/photos/bg3.webp" in html
    assert response.context["calendar_today_label"]
    links = Links()
    links.feed(html)
    assert links.days and len(links.booking) == 1
    for link in links.days + links.booking:
        assert len(parse_qs(urlsplit(link).query)["day"]) == 1
    assert parse_qs(urlsplit(links.booking[0]).query)["book"] == ["1"]


def test_calendar_css_and_images_are_present():
    root = Path(__file__).resolve().parents[1] / "static"
    css = (root / "css" / "editorial-calendar.css").read_text(encoding="utf-8")
    for name in ("bg1.webp", "bg2.webp"):
        assert name in css
    for name in ("bg1.webp", "bg2.webp", "bg3.webp"):
        assert (root / "images" / "photos" / name).is_file()
