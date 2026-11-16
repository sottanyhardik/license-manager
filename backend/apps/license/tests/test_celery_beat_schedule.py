from django.test import SimpleTestCase


class CeleryBeatScheduleTests(SimpleTestCase):
    def test_every_beat_task_is_registered(self):
        from lmanagement.celery import app

        app.loader.import_default_modules()
        registered = set(app.tasks)
        missing = {
            key: entry["task"]
            for key, entry in app.conf.beat_schedule.items()
            if entry["task"] not in registered
        }
        self.assertEqual(missing, {}, f"Beat entries with unregistered tasks: {missing}")
