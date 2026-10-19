"""
Regression tests: audit-log threads must release their Postgres connection.

Each audit write runs in its own thread, which opens its own DB connection.
Django does not close that connection when the thread ends, so the helper must.
"""
import threading
from unittest import mock

from django.test import SimpleTestCase

from apps.core import middleware


class StartLogThreadReleasesConnectionTests(SimpleTestCase):
    def _fake_connection(self):
        closed = threading.Event()
        fake = mock.Mock()
        fake.close.side_effect = closed.set
        return fake, closed

    def test_connection_closed_after_target_runs(self):
        fake, closed = self._fake_connection()
        ran = []

        with mock.patch.object(middleware, 'connection', fake):
            middleware._start_log_thread(ran.append, 'entry')
            self.assertTrue(closed.wait(timeout=5))

        self.assertEqual(ran, ['entry'])

    def test_connection_closed_even_when_target_raises(self):
        fake, closed = self._fake_connection()

        def failing_write():
            raise RuntimeError('audit write failed')

        with mock.patch.object(middleware, 'connection', fake), \
                mock.patch.object(threading, 'excepthook'):
            middleware._start_log_thread(failing_write)
            self.assertTrue(closed.wait(timeout=5))
