from django.apps import AppConfig


class RoutingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'domains.routing'

    def ready(self):
        import os
        import sys
        import threading
        
        is_daphne = any('daphne' in arg for arg in sys.argv)
        is_runserver = os.environ.get('RUN_MAIN') == 'true'
        is_manage_cmd = any(cmd in sys.argv for cmd in ['migrate', 'makemigrations', 'shell', 'collectstatic', 'test', 'check'])
        
        if (is_daphne or is_runserver) and not is_manage_cmd:
            # Run the database seeder asynchronously so it doesn't block server startup
            def run_seed_async():
                try:
                    from scripts.seed_demo import run_seed
                    run_seed(force=False)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Async seeding failed: {e}", exc_info=True)

            threading.Thread(target=run_seed_async, daemon=True).start()
            
            # Start the background GPS simulator loop
            from .simulator import start_gps_simulation
            threading.Thread(target=start_gps_simulation, daemon=True).start()

