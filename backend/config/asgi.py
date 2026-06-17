import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    # 'websocket': URLRouter(...)  # we'll wire this up in Phase 5 once we have a tracking app
})