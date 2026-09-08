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


def test_profiles_share_required_evidence_recall_contract():
    exact, balanced, explore = (answer_mode_profile(mode) for mode in AnswerMode)
    assert {profile.top_dense for profile in (exact, balanced, explore)} == {50}
    assert {profile.top_lexical for profile in (exact, balanced, explore)} == {50}
    assert {profile.top_final for profile in (exact, balanced, explore)} == {10}
    assert {profile.context_budget_tokens for profile in (exact, balanced, explore)} == {4_096}
    assert {profile.dense_rrf_weight for profile in (exact, balanced, explore)} == {1.20}
    assert {profile.lexical_rrf_weight for profile in (exact, balanced, explore)} == {0.80}
