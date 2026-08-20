# Backend Failure-Cluster Ledger

| Cluster | Representative test | Count | Root cause | Code or test | Owner | Result |
| --- | --- | ---: | --- | --- | --- | --- |
| `SYNC_AUTH_CONVERGENCE` | `apps/core/tests/test_sync_failures.py::TestOutOfOrderConvergence::test_in_order_delivery` | 5 captured | Legacy fixture signed server-B/C envelopes with server-A credentials; hardened peer authentication correctly returned 403. | Correct fixture to use the declared source peer credentials; preserve convergence assertions. | durable_sync | Pass (85 sync-failure tests) |
| `SYNC_PULL_SERIALIZATION` | `apps/core/tests/test_sync_failures.py::TestEveryRegisteredMasterIsTransportable::test_null_foreign_key_round_trips_as_null` | 1 captured | Generic serializer emitted an M2M `ManyRelatedManager` (`norms`) into JSON. | Production serialization defect: restrict transport to concrete scalar/FK fields; assert M2M exclusion. | durable_sync | Pass (85 sync-failure tests) |

Capture method: serial pytest using disposable `test_lmanagement_freeze_20260820`, created from `DB_NAME=lmanagement_freeze_20260820`; the local `lmanagement` database was not modified.
