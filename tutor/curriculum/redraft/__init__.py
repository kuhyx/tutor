# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The backfill: every module's cards thrown away and drafted again by Fable.

``python -m tutor redraft start`` snapshots every subject (archived ones
too) into ``$TUTOR_DATA/redraft/`` and queues one unit per module that has
cards. A drainer (``drain``; the live server runs one, a sandbox runs
``redraft drain`` on a copy) builds each unit from the snapshot alone
(``unit``: sources, draft, the seven card rules, the relevance gate, the
old-to-new match, an audit, the cut into modules of at most 12 cards, the
interrogation paths) and swaps it into the subject atomically (``swap``).
Every model reply is cached on disk by its prompt (``replies``), so a
restart resumes at the first call not yet answered and a dry run's replies
replay in the live run. ``redraft report`` writes the proof (``report``).
"""
