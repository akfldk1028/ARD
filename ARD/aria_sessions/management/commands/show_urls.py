from django.core.management.base import BaseCommand
from django.urls import get_resolver

class Command(BaseCommand):
    help = 'Show all URL patterns'

    def handle(self, *args, **options):
        resolver = get_resolver()
        
        def show_urls(urlpatterns, depth=0):
            for pattern in urlpatterns:
                if hasattr(pattern, 'url_patterns'):
                    print("  " * depth + str(pattern.pattern))
                    show_urls(pattern.url_patterns, depth + 1)
                else:
                    print("  " * depth + str(pattern.pattern))
        
        show_urls(resolver.url_patterns)