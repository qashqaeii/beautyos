"""Non-blocking onboarding: the salon setup wizard must never gate dashboard access."""


class OnboardingGateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)
