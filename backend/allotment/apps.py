from django.apps import AppConfig


class AllotmentConfig(AppConfig):
    name = 'allotment'

    def ready(self):
        import allotment.signals  # noqa
