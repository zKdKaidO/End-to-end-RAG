from __future__ import annotations

import pytest

from app.local_compute.answer_modes import AnswerMode, answer_mode_profile
from app.local_compute.errors import LocalComputeError


@pytest.mark.parametrize("mode", [AnswerMode.EXACT, AnswerMode.BALANCED, AnswerMode.EXPLORE])
def test_server_owned_answer_mode_profiles_are_bounded(mode):
    profile = answer_mode_profile(mode)
    assert profile.mode is mode
    assert profile.top_dense > 0 and profile.top_lexical > 0 and profile.top_final > 0
    assert profile.top_final <= profile.top_dense
    assert profile.dense_rrf_weight > 0 and profile.lexical_rrf_weight > 0
    assert profile.top_final <= 10
    assert profile.hierarchy_max_anchors == 10
    assert profile.hierarchy_children_per_anchor == 4


def test_balanced_is_the_backward_compatible_default():
    assert answer_mode_profile(None).mode is AnswerMode.BALANCED


@pytest.mark.parametrize("value", ["", "CUSTOM", 1, {}, "BALANCED "])
def test_arbitrary_browser_tuning_names_are_rejected(value):
    with pytest.raises(LocalComputeError):
        answer_mode_profile(value)


def test_profiles_increase_semantic_recall_without_removing_lexical_retrieval():
    exact, balanced, explore = (answer_mode_profile(mode) for mode in AnswerMode)
    assert exact.top_dense < balanced.top_dense < explore.top_dense
    assert exact.top_lexical < balanced.top_lexical < explore.top_lexical
    assert exact.dense_rrf_weight > balanced.dense_rrf_weight > explore.dense_rrf_weight
    assert exact.lexical_rrf_weight < balanced.lexical_rrf_weight < explore.lexical_rrf_weight
