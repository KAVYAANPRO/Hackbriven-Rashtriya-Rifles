from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.services import content_safety

client = TestClient(app)


@pytest.mark.parametrize("text, category", [
    ("a hot porn video", "sexual"),
    ("NSFW onlyfans style clip", "sexual"),
    ("p0rn compilation", "sexual"),
    ("make a deepfake of the prime minister", "deepfake"),
    ("face swap my boss into a movie", "deepfake"),
    ("graphic gore and beheading", "violence"),
    ("how to make a bomb at home", "dangerous"),
    ("teen porn", "minors"),
])
def test_unsafe_ideas_are_blocked_by_the_keyword_layer(text, category):
    verdict = content_safety.check_rules(text)
    assert not verdict.allowed
    assert verdict.category == category
    assert "Not appropriate video" in verdict.message


@pytest.mark.parametrize("text", [
    "How UPI changed everyday payments in India",
    "Breast cancer awareness month explained",
    "Sex education: what schools should teach",
    "The history of the Second World War",
    "Spotting impersonation scams online",
    "A naked eye guide to the night sky",
])
def test_normal_ideas_are_allowed(text):
    assert content_safety.check_rules(text).allowed


def test_ai_reviewer_can_block_what_keywords_miss():
    ai = content_safety.SafetyVerdict(False, "hate", "ai")
    with patch.object(content_safety.settings, "content_safety_ai", True),          patch.object(content_safety, "check_ai", return_value=ai):
        assert content_safety.review("some subtle idea") == ai


def test_ai_outage_never_blocks_a_creator():
    with patch.object(content_safety.settings, "content_safety_ai", True),          patch.object(content_safety, "check_ai", return_value=None):
        assert content_safety.review("How UPI works").allowed


def test_create_job_rejects_unsafe_topic_with_clear_message_and_no_charge():
    resp = client.post("/jobs", json={"topic": "make a deepfake of a politician"})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["code"] == "content_blocked"
    assert "Not appropriate video" in detail["message"]


def test_boost_rejects_unsafe_prompt():
    resp = client.post("/prompt/boost", json={"prompt": "porn video"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "content_blocked"
