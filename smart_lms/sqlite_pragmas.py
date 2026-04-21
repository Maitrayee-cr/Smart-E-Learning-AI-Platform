from django.db.backends.signals import connection_created
from django.dispatch import receiver


@receiver(connection_created)
def configure_sqlite_pragmas(sender, connection, **kwargs):
    """
    Improve SQLite behavior in local development:
    - WAL: better read/write concurrency
    - busy_timeout: wait for lock release before raising an error
    """
    if connection.vendor != 'sqlite':
        return

    with connection.cursor() as cursor:
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.execute('PRAGMA synchronous=NORMAL;')
        cursor.execute('PRAGMA busy_timeout=30000;')
