# SEC-04 (improvement) — Login throttle is IP-keyed only, no per-account limit

## Location
`backend/apps/core/throttling.py:195-215` (`LoginRateThrottle.get_cache_key`
uses `self.get_ident(request)` — client IP — as the only cache key).
`backend/lmanagement/settings.py` `DEFAULT_THROTTLE_RATES["login"] = "10/minute"`.

## What & why
10 login attempts/minute per source IP is reasonable against a single-source
brute force, but a distributed credential-stuffing attack (many source IPs,
each staying under 10/min) can still make an effectively unlimited number of
attempts against one specific username, since there is no per-account
(username-keyed) counter layered on top of the per-IP one.

## Risk
Lower-likelihood but real: credential stuffing / targeted password guessing
against a specific known username from many IPs (botnet, proxy rotation)
is not rate-limited at the account level.

## Mitigation recommendation
Add a second, username-keyed throttle/lockout counter (e.g. N failed
attempts per username per hour triggers a short account-level cooldown or a
step-up challenge), independent of source IP. This is additive and does not
change any existing request/response contract.

## Confidence
High that the code only keys by IP (verified from source). Medium on
real-world exploitability, since it also requires the attacker to already
know a valid username.

## Classification
Improvement (defense-in-depth hardening), not a defect — the existing IP-based
throttle is a legitimate control, just not layered with account-level
protection.
