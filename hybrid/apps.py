from django.apps import AppConfig


class HybridConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hybrid'

    def ready(self):
        # Stage 3 Checkpoint 3.1: register the simulator creation-evidence
        # capture receivers exactly once per process. dispatch_uid inside the
        # module makes the connection itself idempotent as well.
        from hybrid import creation_ledger

        creation_ledger.register_capture_receivers()
