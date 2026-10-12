# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The Firebase RTDB relay: phone and desktop clients talk to the PC worker.

``DOCS-contract.md`` is the protocol. Clients PUT requests under
``/tutor/v1/requests``; the worker claims them, runs them on the one
:class:`~tutor.engine.Engine`, commits locally and publishes a read-only
projection of sessions, history and stats back to RTDB.
"""
