from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    label = 'core'
    verbose_name = 'Core'

    def ready(self):
        # Register DB connection pragmas for local SQLite stability.
        import smart_lms.sqlite_pragmas  # noqa: F401
