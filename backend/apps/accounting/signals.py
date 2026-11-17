"""Trade-side guards are implemented as on_delete handlers (models/guards.py) and PROTECT FKs,
because Django evaluates on_delete before pre_delete signals. Nothing is registered here; the
module is kept so AppConfig.ready() has a stable import target for future receivers.
"""
