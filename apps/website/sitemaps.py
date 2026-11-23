from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.salons.models import Salon
from apps.website.models import BlogPost


class StaticPublicSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return ["home", "features", "blog", "faq", "contact", "privacy", "terms"]

    def location(self, name):
        return reverse(f"website:{name}")


class PublishedBlogSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return BlogPost.published_qs().order_by("pk")

    def lastmod(self, post):
        return post.updated_at

    def location(self, post):
        return reverse("website:blog_post", kwargs={"slug": post.slug})


class ActiveSalonSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return Salon.objects.filter(
            is_active=True, is_accepting_bookings=True,
            settings__onboarding_completed_at__isnull=False,
        ).order_by("pk")

    def lastmod(self, salon):
        return salon.updated_at

    def location(self, salon):
        return salon.get_public_url()


SITEMAPS = {
    "pages": StaticPublicSitemap,
    "blog": PublishedBlogSitemap,
    "salons": ActiveSalonSitemap,
}
