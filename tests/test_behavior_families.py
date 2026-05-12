from __future__ import annotations

from aria.core.behavior_families import behavior_family_id_for
from aria.core.behavior_families import mailbox_access_mode
from aria.core.behavior_families import request_target_mode
from aria.core.behavior_families import source_lookup_mode


def test_behavior_family_groups_rss_and_website_under_source_lookup() -> None:
    assert behavior_family_id_for(behavior_profile="rss_read_feed") == "source_lookup"
    assert behavior_family_id_for(behavior_profile="website_read") == "source_lookup"
    assert behavior_family_id_for(behavior_profile="website_list") == "source_lookup"


def test_source_lookup_mode_maps_digest_reference_and_listing() -> None:
    assert source_lookup_mode(behavior_profile="rss_read_feed") == "digest"
    assert source_lookup_mode(plan_class="website_reference") == "reference"
    assert source_lookup_mode(plan_class="website_listing") == "listing"


def test_behavior_family_groups_imap_under_mailbox_access() -> None:
    assert behavior_family_id_for(behavior_profile="imap_read_mailbox") == "mailbox_access"
    assert behavior_family_id_for(behavior_profile="imap_search_mailbox") == "mailbox_access"


def test_mailbox_access_mode_maps_read_and_search() -> None:
    assert mailbox_access_mode(behavior_profile="imap_read_mailbox") == "read"
    assert mailbox_access_mode(plan_class="mailbox_search_basic") == "search"


def test_behavior_family_groups_http_api_under_request_target() -> None:
    assert behavior_family_id_for(behavior_profile="http_api_request") == "request_target"


def test_request_target_mode_maps_api_request() -> None:
    assert request_target_mode(behavior_profile="http_api_request") == "request"
    assert request_target_mode(plan_class="api_request_basic") == "request"
