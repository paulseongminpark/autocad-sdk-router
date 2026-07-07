#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TRACK-4 spec-presence gate -- the Daedalus corpus-run execution plan.

Intent (WHY): the 414-file corpus batch run is an OPERATIONAL milestone; its
execution plan (inputs, resumable ledger, aggregation, failure isolation,
honest throughput limits) must exist as a reviewed artifact BEFORE any real
corpus run is launched, so the run is reproducible and its limits are stated
up front (no fake completeness). This test pins the artifact + its required
sections.
"""
from __future__ import annotations

import os
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_SPEC = os.path.join(_REPO, "reports", "specs_w7", "daedalus_corpus_run.md")
_REQUIRED_SECTIONS = ("Inputs", "Ledger", "Aggregation", "Failure isolation", "Limits")


class TestDaedalusCorpusRunSpec(unittest.TestCase):
    def test_spec_exists_and_is_substantial(self):
        self.assertTrue(os.path.isfile(_SPEC), "corpus-run spec missing: %s" % _SPEC)
        text = open(_SPEC, encoding="utf-8").read()
        self.assertGreater(len(text), 2500, "spec too thin to be a real execution plan")

    def test_spec_has_required_sections(self):
        text = open(_SPEC, encoding="utf-8").read()
        missing = [s for s in _REQUIRED_SECTIONS if s not in text]
        self.assertEqual(missing, [], "spec missing sections: %r" % missing)


if __name__ == "__main__":
    unittest.main()
