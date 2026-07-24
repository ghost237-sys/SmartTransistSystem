from django.apps import AppConfig


class RoutingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'domains.routing'

    def ready(self):
        pass
