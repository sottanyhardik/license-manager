"""
Module 04 — **Media transfer** tests (media.py) with real files on disk.

Media sync is the part of Module 04 that moves bytes rather than rows: company
logos, signatures, stamps and transfer letters.  Only ``create_media_tasks`` had
any coverage, so the actual transfer — download, SHA256 verification, saving to
the model field, retry and give-up — was entirely untested.

Everything here uses a real ``MEDIA_ROOT`` (a tmp dir), real ``FileField`` /
``ImageField`` writes and real SHA256 digests; only ``urlopen`` is faked, and
several tests feed the client's URL into the real download endpoint so the two
halves of the transfer are proven to fit together.
"""
from __future__ import annotations

import hashlib

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone

from apps.core.models import CompanyModel, MasterChange, TransferLetterModel
from apps.core.sync.media import (
    MAX_RETRY_ATTEMPTS,
    create_media_tasks,
    download_media_from_peer,
    get_media_info,
    get_pending_media_tasks,
    process_media_task,
    run_media_sync_worker,
)
from apps.core.sync.models import MediaSyncTask
from apps.core.sync.registry import get_entry
from apps.core.tests.sync_factories import (  # noqa: F401  (fixtures imported by name)
    FakeHTTPResponse,
    api,
    auth_client,
    company_event,
    connection_refused,
    http_error,
    locmem_cache,
    make_peer,
    media_root,
    push_payload,
    query_params_of,
    read_timeout,
    request_headers,
    sent_requests,
    sha256_of,
    sync_event,
    patched_urlopen,
    write_media,
)

pytestmark = pytest.mark.django_db

LOGO = b"\x89PNG\r\n\x1a\n" + b"logo-payload" * 20
LETTER = b"%PDF-1.4 transfer-letter " + bytes(range(256))


def _task(**overrides) -> MediaSyncTask:
    defaults = dict(
        model_label="core.TransferLetterModel",
        natural_key="TL-1",
        field_name="tl",
        source_server="peer-B",
        source_path="peerfiles/letter.pdf",
        expected_sha256=sha256_of(LETTER),
    )
    defaults.update(overrides)
    return MediaSyncTask.objects.create(**defaults)


# ── get_media_info (outbound metadata) ─────────────────────────────────

class TestGetMediaInfo:
    def test_empty_fields_report_none(self, media_root):
        company = CompanyModel.objects.create(iec="MED000001", name="No Media")
        info = get_media_info(company, get_entry("core.CompanyModel"))

        assert set(info) == {"logo", "signature", "stamp"}
        assert all(v is None for v in info.values())

    def test_populated_field_reports_path_and_sha256(self, media_root):
        company = CompanyModel.objects.create(iec="MED000002", name="With Logo")
        company.logo.save("logo.png", ContentFile(LOGO), save=True)

        info = get_media_info(company, get_entry("core.CompanyModel"))

        assert info["logo"]["path"] == company.logo.name
        assert info["logo"]["sha256"] == hashlib.sha256(LOGO).hexdigest()
        assert info["signature"] is None

    def test_sha256_is_computed_from_the_bytes_on_disk(self, media_root):
        letter = TransferLetterModel.objects.create(name="TL-SHA")
        letter.tl.save("letter.pdf", ContentFile(LETTER), save=True)

        info = get_media_info(letter, get_entry("core.TransferLetterModel"))
        on_disk = (media_root / letter.tl.name).read_bytes()

        assert info["tl"]["sha256"] == sha256_of(on_disk)

    def test_missing_file_on_disk_yields_a_blank_digest(self, media_root):
        """Documents current behaviour: a dangling reference is still shipped,
        but with no digest, so the receiver cannot verify it."""
        company = CompanyModel.objects.create(iec="MED000003", name="Dangling")
        company.logo.name = "companies/999/gone.png"
        company.save(update_fields=["logo"])

        info = get_media_info(company, get_entry("core.CompanyModel"))
        assert info["logo"]["path"] == "companies/999/gone.png"
        assert info["logo"]["sha256"] == ""


# ── create_media_tasks (queueing) ──────────────────────────────────────

class TestCreateMediaTasks:
    def test_one_task_per_populated_field(self):
        tasks = create_media_tasks(
            "core.CompanyModel", "MED000010",
            {
                "logo": {"path": "companies/1/logo.png", "sha256": "a" * 64},
                "signature": {"path": "companies/1/sig.png", "sha256": "b" * 64},
                "stamp": None,
            },
            "peer-B",
        )
        assert {t.field_name for t in tasks} == {"logo", "signature"}
        assert MediaSyncTask.objects.count() == 2

    @pytest.mark.parametrize("info", [None, {}, {"path": ""}, {"path": None}, {"sha256": "x"}])
    def test_fields_without_a_path_are_ignored(self, info):
        assert create_media_tasks("core.CompanyModel", "MED000011", {"logo": info}, "peer-B") == []
        assert MediaSyncTask.objects.count() == 0

    def test_a_new_path_queues_a_new_task_replacement(self):
        create_media_tasks(
            "core.CompanyModel", "MED000012",
            {"logo": {"path": "companies/1/v1.png", "sha256": "a" * 64}}, "peer-B",
        )
        second = create_media_tasks(
            "core.CompanyModel", "MED000012",
            {"logo": {"path": "companies/1/v2.png", "sha256": "c" * 64}}, "peer-B",
        )
        assert len(second) == 1
        assert MediaSyncTask.objects.count() == 2

    def test_repeating_a_completed_transfer_is_queued_again(self):
        first = create_media_tasks(
            "core.CompanyModel", "MED000013",
            {"logo": {"path": "companies/1/v1.png", "sha256": "a" * 64}}, "peer-B",
        )[0]
        first.status = MediaSyncTask.STATUS_COMPLETE
        first.save(update_fields=["status"])

        again = create_media_tasks(
            "core.CompanyModel", "MED000013",
            {"logo": {"path": "companies/1/v1.png", "sha256": "a" * 64}}, "peer-B",
        )
        assert len(again) == 1

    def test_in_progress_transfer_is_not_duplicated(self):
        first = create_media_tasks(
            "core.CompanyModel", "MED000014",
            {"logo": {"path": "companies/1/v1.png", "sha256": "a" * 64}}, "peer-B",
        )[0]
        first.status = MediaSyncTask.STATUS_IN_PROGRESS
        first.save(update_fields=["status"])

        assert create_media_tasks(
            "core.CompanyModel", "MED000014",
            {"logo": {"path": "companies/1/v1.png", "sha256": "a" * 64}}, "peer-B",
        ) == []


class TestPendingQueue:
    def test_pending_tasks_come_back_oldest_first(self):
        old = _task(natural_key="TL-old")
        MediaSyncTask.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timezone.timedelta(hours=1),
        )
        new = _task(natural_key="TL-new")

        assert [t.pk for t in get_pending_media_tasks()] == [old.pk, new.pk]

    def test_only_pending_tasks_are_returned(self):
        _task(natural_key="TL-pending")
        _task(natural_key="TL-done", status=MediaSyncTask.STATUS_COMPLETE)
        _task(natural_key="TL-failed", status=MediaSyncTask.STATUS_FAILED)

        assert [t.natural_key for t in get_pending_media_tasks()] == ["TL-pending"]

    def test_limit_is_honoured(self):
        for i in range(5):
            _task(natural_key=f"TL-{i}")
        assert len(get_pending_media_tasks(limit=2)) == 2


# ── process_media_task (verification + save) ────────────────────────────

class TestProcessMediaTask:
    def test_successful_transfer_saves_the_file_and_completes(self, media_root):
        letter = TransferLetterModel.objects.create(name="TL-OK")
        task = _task(natural_key="TL-OK")

        assert process_media_task(task, LETTER) is True

        task.refresh_from_db()
        assert task.status == MediaSyncTask.STATUS_COMPLETE
        assert task.completed_at is not None
        assert task.attempts == 1
        assert task.last_error == ""

        letter.refresh_from_db()
        assert letter.tl.name
        assert (media_root / letter.tl.name).read_bytes() == LETTER

    def test_sha256_matches_after_transfer(self, media_root):
        TransferLetterModel.objects.create(name="TL-SHA-EQ")
        task = _task(natural_key="TL-SHA-EQ")
        process_media_task(task, LETTER)

        letter = TransferLetterModel.objects.get(name="TL-SHA-EQ")
        from apps.core.sync.mixins import media_sha256
        assert media_sha256(letter.tl) == task.expected_sha256

    def test_image_field_master_is_supported(self, media_root):
        company = CompanyModel.objects.create(iec="MED000020", name="Logo Co")
        task = _task(
            model_label="core.CompanyModel", natural_key="MED000020",
            field_name="logo", source_path="peerfiles/logo.png",
            expected_sha256=sha256_of(LOGO),
        )

        assert process_media_task(task, LOGO) is True

        company.refresh_from_db()
        assert (media_root / company.logo.name).read_bytes() == LOGO
        assert company.logo.name.endswith(".png")

    def test_corrupt_content_is_rejected_and_nothing_is_written(self, media_root):
        letter = TransferLetterModel.objects.create(name="TL-CORRUPT")
        task = _task(natural_key="TL-CORRUPT")

        assert process_media_task(task, b"tampered bytes") is False

        task.refresh_from_db()
        assert task.status == MediaSyncTask.STATUS_PENDING       # retryable
        assert task.attempts == 1
        assert "SHA256 mismatch" in task.last_error
        assert task.expected_sha256 in task.last_error

        letter.refresh_from_db()
        assert not letter.tl.name, "corrupt payload must not reach the model"

    def test_corrupt_content_never_overwrites_a_good_file(self, media_root):
        letter = TransferLetterModel.objects.create(name="TL-KEEP")
        letter.tl.save("good.pdf", ContentFile(b"the good version"), save=True)
        good_name = letter.tl.name

        task = _task(natural_key="TL-KEEP")
        assert process_media_task(task, b"tampered") is False

        letter.refresh_from_db()
        assert letter.tl.name == good_name
        assert (media_root / good_name).read_bytes() == b"the good version"

    def test_blank_expected_digest_skips_verification(self, media_root):
        """Documents current behaviour: no digest → no integrity check."""
        TransferLetterModel.objects.create(name="TL-NOSHA")
        task = _task(natural_key="TL-NOSHA", expected_sha256="")

        assert process_media_task(task, b"whatever") is True
        task.refresh_from_db()
        assert task.status == MediaSyncTask.STATUS_COMPLETE

    def test_unknown_model_label_fails_cleanly(self, media_root):
        task = _task(model_label="core.NotAModel", expected_sha256="")
        assert process_media_task(task, b"x") is False

        task.refresh_from_db()
        assert "Unknown model_label" in task.last_error
        assert task.status == MediaSyncTask.STATUS_PENDING

    def test_missing_target_record_fails_cleanly_then_succeeds_later(self, media_root):
        """The push view queues media *before* the row is applied, so the first
        attempt can legitimately lose the race."""
        task = _task(natural_key="TL-RACE")

        assert process_media_task(task, LETTER) is False
        task.refresh_from_db()
        assert task.status == MediaSyncTask.STATUS_PENDING
        assert "DoesNotExist" in task.last_error or "matching query" in task.last_error

        TransferLetterModel.objects.create(name="TL-RACE")
        assert process_media_task(task, LETTER) is True

        task.refresh_from_db()
        assert task.status == MediaSyncTask.STATUS_COMPLETE
        assert task.attempts == 2

    def test_attempts_accumulate_until_the_task_is_marked_failed(self, media_root):
        TransferLetterModel.objects.create(name="TL-GIVEUP")
        task = _task(natural_key="TL-GIVEUP")

        for attempt in range(1, MAX_RETRY_ATTEMPTS):
            assert process_media_task(task, b"bad") is False
            task.refresh_from_db()
            assert task.attempts == attempt
            assert task.status == MediaSyncTask.STATUS_PENDING

        assert process_media_task(task, b"bad") is False
        task.refresh_from_db()
        assert task.attempts == MAX_RETRY_ATTEMPTS
        assert task.status == MediaSyncTask.STATUS_FAILED

    def test_failed_tasks_are_not_retried_by_the_worker(self, media_root):
        _task(natural_key="TL-DEAD", status=MediaSyncTask.STATUS_FAILED, attempts=5)
        with patched_urlopen(response=FakeHTTPResponse(LETTER)) as urlopen:
            run_media_sync_worker()
        urlopen.assert_not_called()

    def test_reprocessing_a_completed_task_is_idempotent(self, media_root):
        TransferLetterModel.objects.create(name="TL-IDEM")
        task = _task(natural_key="TL-IDEM")

        assert process_media_task(task, LETTER) is True
        first_name = TransferLetterModel.objects.get(name="TL-IDEM").tl.name

        # Same bytes again: still verifies, still one row, content unchanged.
        assert process_media_task(task, LETTER) is True
        letter = TransferLetterModel.objects.get(name="TL-IDEM")
        assert (media_root / letter.tl.name).read_bytes() == LETTER
        assert sha256_of((media_root / first_name).read_bytes()) == task.expected_sha256
        assert MediaSyncTask.objects.count() == 1


# ── download_media_from_peer (the wire) ────────────────────────────────

class TestDownloadMediaFromPeer:
    def test_returns_the_bytes(self, media_root):
        peer = make_peer("peer-B")
        with patched_urlopen(response=FakeHTTPResponse(LETTER)):
            assert download_media_from_peer(peer, "peerfiles/letter.pdf") == LETTER

    def test_request_targets_the_peers_download_endpoint_with_auth(self, media_root):
        peer = make_peer("peer-B", base_url="http://b.example.test/", auth_token="tok")
        with patched_urlopen(response=FakeHTTPResponse(LETTER)) as urlopen:
            download_media_from_peer(peer, "peerfiles/letter.pdf")

        request = sent_requests(urlopen)[0]
        assert request.full_url.startswith("http://b.example.test/api/sync/media/download/?")
        assert query_params_of(request.full_url) == {"path": "peerfiles/letter.pdf"}
        assert request_headers(request)["authorization"] == "Bearer tok"

    @pytest.mark.parametrize("boom", ["refused", "timeout", "404", "500"])
    def test_transport_failures_return_none(self, media_root, boom):
        peer = make_peer("peer-B")
        cases = {
            "refused": connection_refused(),
            "timeout": read_timeout(),
            "404": http_error(404),
            "500": http_error(500),
        }
        with patched_urlopen(side_effect=cases[boom]):
            assert download_media_from_peer(peer, "peerfiles/gone.pdf") is None

    @pytest.mark.parametrize("filename", [
        "plain.png",
        "with space.png",
        "logo&stamp.png",
        "a+b.png",
        "100%pure.png",
        "quote'name.png",
        "ünïcode.png",
    ])
    def test_url_is_encoded_so_the_peer_serves_the_right_file(
        self, api, media_root, filename,
    ):
        """Regression: the path was interpolated into the URL raw, so "&" ended
        the parameter and "+" was decoded as a space — the peer answered 404 or
        served a different file, and media silently never replicated."""
        content = f"content of {filename}".encode()
        rel = write_media(media_root, f"peerfiles/{filename}", content)
        peer = make_peer("peer-B", base_url="http://b.example.test")

        with patched_urlopen(response=FakeHTTPResponse(content)) as urlopen:
            download_media_from_peer(peer, rel)
        query = sent_requests(urlopen)[0].full_url.split("?", 1)[1]

        # Replay the client's own query string against the real endpoint.
        response = api.get(f"{reverse('sync:sync-media-download')}?{query}")

        assert response.status_code == 200, f"{filename!r} → {response.status_code}"
        assert b"".join(response.streaming_content) == content


# ── run_media_sync_worker (the loop) ───────────────────────────────────

class TestMediaSyncWorker:
    def test_no_pending_tasks_makes_no_requests(self, media_root):
        with patched_urlopen(response=FakeHTTPResponse(LETTER)) as urlopen:
            run_media_sync_worker()
        urlopen.assert_not_called()

    def test_downloads_and_saves_every_pending_task(self, media_root):
        make_peer("peer-B")
        TransferLetterModel.objects.create(name="TL-W1")
        TransferLetterModel.objects.create(name="TL-W2")
        _task(natural_key="TL-W1")
        _task(natural_key="TL-W2")

        with patched_urlopen(response=FakeHTTPResponse(LETTER)) as urlopen:
            run_media_sync_worker()

        assert urlopen.call_count == 2
        assert MediaSyncTask.objects.filter(status=MediaSyncTask.STATUS_COMPLETE).count() == 2
        for name in ["TL-W1", "TL-W2"]:
            letter = TransferLetterModel.objects.get(name=name)
            assert (media_root / letter.tl.name).read_bytes() == LETTER

    def test_tasks_are_grouped_by_source_server(self, media_root):
        make_peer("peer-B", base_url="http://b.example.test")
        make_peer("peer-C", base_url="http://c.example.test")
        TransferLetterModel.objects.create(name="TL-B")
        TransferLetterModel.objects.create(name="TL-C")
        _task(natural_key="TL-B", source_server="peer-B")
        _task(natural_key="TL-C", source_server="peer-C")

        with patched_urlopen(response=FakeHTTPResponse(LETTER)) as urlopen:
            run_media_sync_worker()

        hosts = {r.full_url.split("/api/")[0] for r in sent_requests(urlopen)}
        assert hosts == {"http://b.example.test", "http://c.example.test"}

    def test_unknown_source_server_records_an_error_without_downloading(self, media_root):
        _task(natural_key="TL-NOPEER", source_server="never-registered")

        with patched_urlopen(response=FakeHTTPResponse(LETTER)) as urlopen:
            run_media_sync_worker()

        urlopen.assert_not_called()
        task = MediaSyncTask.objects.get(natural_key="TL-NOPEER")
        assert "No active peer" in task.last_error
        # Documents current behaviour: still pending, no attempt consumed.
        assert task.status == MediaSyncTask.STATUS_PENDING
        assert task.attempts == 0

    def test_inactive_peer_is_treated_as_unknown(self, media_root):
        make_peer("peer-B", is_active=False)
        _task(natural_key="TL-INACTIVE")

        with patched_urlopen(response=FakeHTTPResponse(LETTER)) as urlopen:
            run_media_sync_worker()

        urlopen.assert_not_called()
        assert "No active peer" in MediaSyncTask.objects.get(natural_key="TL-INACTIVE").last_error

    def test_download_failure_consumes_an_attempt_and_stays_pending(self, media_root):
        make_peer("peer-B")
        TransferLetterModel.objects.create(name="TL-DLFAIL")
        _task(natural_key="TL-DLFAIL")

        with patched_urlopen(side_effect=http_error(404)):
            run_media_sync_worker()

        task = MediaSyncTask.objects.get(natural_key="TL-DLFAIL")
        assert task.status == MediaSyncTask.STATUS_PENDING
        assert task.attempts == 1
        assert task.last_error == "Download returned None"

    def test_a_slow_peer_does_not_abort_the_worker(self, media_root):
        """Regression: a socket read timeout raises TimeoutError, which the
        downloader did not catch — it escaped ``run_media_sync_worker`` and every
        remaining task in the pass was silently skipped."""
        make_peer("peer-B")
        TransferLetterModel.objects.create(name="TL-SLOW")
        TransferLetterModel.objects.create(name="TL-AFTER")
        _task(natural_key="TL-SLOW")
        _task(natural_key="TL-AFTER")

        with patched_urlopen(responses=[read_timeout(), FakeHTTPResponse(LETTER)]):
            run_media_sync_worker()

        slow = MediaSyncTask.objects.get(natural_key="TL-SLOW")
        assert slow.status == MediaSyncTask.STATUS_PENDING
        assert slow.attempts == 1
        after = MediaSyncTask.objects.get(natural_key="TL-AFTER")
        assert after.status == MediaSyncTask.STATUS_COMPLETE, (
            "a timeout on one task must not starve the rest of the queue"
        )

    def test_repeated_download_failures_end_in_failed(self, media_root):
        make_peer("peer-B")
        TransferLetterModel.objects.create(name="TL-DLDEAD")
        _task(natural_key="TL-DLDEAD")

        for _ in range(MAX_RETRY_ATTEMPTS):
            with patched_urlopen(side_effect=connection_refused()):
                run_media_sync_worker()

        task = MediaSyncTask.objects.get(natural_key="TL-DLDEAD")
        assert task.attempts == MAX_RETRY_ATTEMPTS
        assert task.status == MediaSyncTask.STATUS_FAILED

    def test_a_failing_task_does_not_starve_the_others(self, media_root):
        make_peer("peer-B")
        TransferLetterModel.objects.create(name="TL-GOOD")
        _task(natural_key="TL-BADSHA", expected_sha256="f" * 64)
        _task(natural_key="TL-GOOD")

        with patched_urlopen(response=FakeHTTPResponse(LETTER)):
            run_media_sync_worker()

        assert MediaSyncTask.objects.get(natural_key="TL-GOOD").status == MediaSyncTask.STATUS_COMPLETE
        assert MediaSyncTask.objects.get(natural_key="TL-BADSHA").status == MediaSyncTask.STATUS_PENDING

    def test_second_worker_pass_does_not_re_download_completed_work(self, media_root):
        make_peer("peer-B")
        TransferLetterModel.objects.create(name="TL-ONCE")
        _task(natural_key="TL-ONCE")

        with patched_urlopen(response=FakeHTTPResponse(LETTER)) as first:
            run_media_sync_worker()
        with patched_urlopen(response=FakeHTTPResponse(LETTER)) as second:
            run_media_sync_worker()

        assert first.call_count == 1
        assert second.call_count == 0


# ── full lifecycle over the API + worker ───────────────────────────────

class TestMediaLifecycleEndToEnd:
    def _push(self, api, event):
        response = api.post(reverse("sync:sync-push"), push_payload(event), format="json")
        assert response.status_code == 200, response.data
        return response

    def test_create_update_replace_delete(self, api, media_root):
        make_peer("server-A")

        v1 = b"letter version one"
        v2 = b"letter version two"
        write_media(media_root, "peerfiles/v1.pdf", v1)
        write_media(media_root, "peerfiles/v2.pdf", v2)

        # ── CREATE: row + media metadata arrive together ────────────────
        self._push(api, sync_event(
            "core.TransferLetterModel", "create", {"name": "TL-LIFE"},
            version=1, media={"tl": {"path": "peerfiles/v1.pdf", "sha256": sha256_of(v1)}},
        ))
        assert TransferLetterModel.objects.filter(name="TL-LIFE").exists()
        assert MediaSyncTask.objects.filter(natural_key="TL-LIFE").count() == 1

        with patched_urlopen(response=FakeHTTPResponse(v1)):
            run_media_sync_worker()

        letter = TransferLetterModel.objects.get(name="TL-LIFE")
        assert (media_root / letter.tl.name).read_bytes() == v1

        # ── UPDATE with no media change: no new transfer ────────────────
        self._push(api, sync_event(
            "core.TransferLetterModel", "update", {"name": "TL-LIFE"}, version=2,
        ))
        assert MediaSyncTask.objects.filter(natural_key="TL-LIFE").count() == 1

        # ── REPLACE: new path → new transfer, new bytes win ─────────────
        self._push(api, sync_event(
            "core.TransferLetterModel", "update", {"name": "TL-LIFE"}, version=3,
            media={"tl": {"path": "peerfiles/v2.pdf", "sha256": sha256_of(v2)}},
        ))
        assert MediaSyncTask.objects.filter(natural_key="TL-LIFE").count() == 2

        with patched_urlopen(response=FakeHTTPResponse(v2)):
            run_media_sync_worker()

        letter.refresh_from_db()
        assert (media_root / letter.tl.name).read_bytes() == v2
        assert MediaSyncTask.objects.filter(
            natural_key="TL-LIFE", status=MediaSyncTask.STATUS_COMPLETE,
        ).count() == 2

        # ── DELETE: row is tombstoned, bytes are kept, nothing queued ──
        stored = letter.tl.name
        self._push(api, sync_event(
            "core.TransferLetterModel", "delete", {"name": "TL-LIFE"}, version=4,
        ))
        letter.refresh_from_db()
        assert letter.is_tombstone is True
        assert (media_root / stored).exists(), "tombstone must not destroy the file"
        assert MediaSyncTask.objects.filter(natural_key="TL-LIFE").count() == 2

    def test_pull_events_carry_media_metadata(self, api, media_root):
        """Regression: outbound events never included ``media``, so a peer could
        never learn a file existed and the whole transfer pipeline was dead."""
        company = CompanyModel.objects.create(iec="MED000030", name="Pull Media")
        company.logo.save("logo.png", ContentFile(LOGO), save=True)
        MasterChange.objects.create(
            model_label="core.CompanyModel", natural_key="MED000030",
            op=MasterChange.OP_CREATE,
        )

        response = api.get(reverse("sync:sync-pull"))
        event = [e for e in response.data["events"]
                 if e["data"].get("iec") == "MED000030"][0]

        assert "media" in event, "pull event has no media metadata"
        assert event["media"]["logo"]["path"] == company.logo.name
        assert event["media"]["logo"]["sha256"] == sha256_of(LOGO)
        assert event["media"]["signature"] is None

    def test_events_without_media_stay_lean(self, api, media_root):
        CompanyModel.objects.create(iec="MED000031", name="No Media")
        MasterChange.objects.create(
            model_label="core.CompanyModel", natural_key="MED000031",
            op=MasterChange.OP_CREATE,
        )
        event = [e for e in api.get(reverse("sync:sync-pull")).data["events"]
                 if e["data"].get("iec") == "MED000031"][0]
        assert "media" not in event

    def test_pulled_metadata_drives_a_verified_transfer(self, api, media_root):
        """pull → push → MediaSyncTask → download → SHA256 verified save."""
        make_peer("peer-B", base_url="http://b.example.test")
        api.credentials(
            HTTP_X_SYNC_SERVER_ID="peer-B",
            HTTP_AUTHORIZATION="Bearer peer-b-token",
        )
        source = CompanyModel.objects.create(iec="MED000032", name="Source Co")
        source.logo.save("logo.png", ContentFile(LOGO), save=True)
        MasterChange.objects.create(
            model_label="core.CompanyModel", natural_key="MED000032",
            op=MasterChange.OP_CREATE,
        )

        pulled = [e for e in api.get(reverse("sync:sync-pull")).data["events"]
                  if e["data"].get("iec") == "MED000032"][0]

        # Deliver that same event to the (local) push endpoint, as a peer would.
        response = api.post(
            reverse("sync:sync-push"),
            push_payload({**pulled, "source_server": "peer-B"}, source_server="peer-B"),
            format="json",
        )
        assert response.status_code == 200, response.data

        task = MediaSyncTask.objects.get(model_label="core.CompanyModel", field_name="logo")
        assert task.expected_sha256 == sha256_of(LOGO)
        assert task.source_server == "peer-B"

        with patched_urlopen(response=FakeHTTPResponse(LOGO)) as urlopen:
            run_media_sync_worker()

        assert query_params_of(sent_requests(urlopen)[0].full_url)["path"] == source.logo.name

        task.refresh_from_db()
        assert task.status == MediaSyncTask.STATUS_COMPLETE
        company = CompanyModel.objects.get(iec="MED000032")
        assert (media_root / company.logo.name).read_bytes() == LOGO

    def test_tampered_delivery_is_refused_end_to_end(self, api, media_root):
        make_peer("server-A")
        TransferLetterModel.objects.create(name="TL-TAMPER")
        self._push(api, sync_event(
            "core.TransferLetterModel", "update", {"name": "TL-TAMPER"}, version=2,
            media={"tl": {"path": "peerfiles/real.pdf", "sha256": sha256_of(LETTER)}},
        ))

        with patched_urlopen(response=FakeHTTPResponse(b"man in the middle")):
            run_media_sync_worker()

        task = MediaSyncTask.objects.get(natural_key="TL-TAMPER")
        assert task.status == MediaSyncTask.STATUS_PENDING
        assert "SHA256 mismatch" in task.last_error
        assert not TransferLetterModel.objects.get(name="TL-TAMPER").tl.name
