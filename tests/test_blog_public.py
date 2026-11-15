import pytest
from django.urls import reverse
from django.utils import timezone

from apps.website.models import BlogPost


@pytest.mark.django_db
def test_draft_post_not_public(client):
    BlogPost.objects.create(
        title="مخفی",
        slug="hidden",
        body="متن",
        status=BlogPost.Status.DRAFT,
    )
    assert client.get(reverse("website:blog_post", kwargs={"slug": "hidden"})).status_code == 404


@pytest.mark.django_db
def test_published_post_visible(client):
    BlogPost.objects.create(
        title="عمومی",
        slug="public-post",
        body="محتوای تست",
        summary="خلاصه",
        category="راهنما",
        status=BlogPost.Status.PUBLISHED,
        published_at=timezone.now(),
    )
    assert client.get(reverse("website:blog_post", kwargs={"slug": "public-post"})).status_code == 200
    assert client.get(reverse("website:blog")).status_code == 200