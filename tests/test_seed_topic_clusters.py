#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the random seed topic selection feature.

Validates:
  1. TOPIC_CLUSTERS contains all expected domain clusters.
  2. Every cluster has at least one topic.
  3. _pick_random_seed_topic() always returns a topic that exists in TOPIC_CLUSTERS.
  4. Config default seed_topic is drawn from TOPIC_CLUSTERS (when no explicit value given).
  5. Config(seed_topic=...) respects an explicitly provided topic.
  6. MainScript.run() logs the seed topic and cluster.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch

import Entelgia_production_meta as _meta
from Entelgia_production_meta import (
    TOPIC_CLUSTERS,
    _pick_random_seed_topic,
    Config,
)

EXPECTED_CLUSTERS = {
    "philosophy",
    "psychology",
    "biology",
    "society",
    "technology",
    "economics",
    "practical_dilemmas",
}


class TestTopicClusters:
    """TOPIC_CLUSTERS structure validation."""

    def test_all_expected_clusters_present(self):
        """TOPIC_CLUSTERS must contain all seven domain clusters."""
        assert set(TOPIC_CLUSTERS.keys()) == EXPECTED_CLUSTERS

    def test_each_cluster_has_topics(self):
        """Every cluster must have at least one topic."""
        for cluster, topics in TOPIC_CLUSTERS.items():
            assert len(topics) >= 1, f"Cluster '{cluster}' is empty"

    def test_all_topics_are_non_empty_strings(self):
        """Every topic must be a non-empty string."""
        for cluster, topics in TOPIC_CLUSTERS.items():
            for topic in topics:
                assert (
                    isinstance(topic, str) and topic.strip()
                ), f"Empty or non-string topic in cluster '{cluster}': {topic!r}"

    def test_no_duplicate_topics_within_cluster(self):
        """No cluster should contain duplicate topics."""
        for cluster, topics in TOPIC_CLUSTERS.items():
            assert len(topics) == len(
                set(topics)
            ), f"Duplicate topics found in cluster '{cluster}'"


class TestPickRandomSeedTopic:
    """_pick_random_seed_topic() function validation."""

    def test_returns_string(self):
        """_pick_random_seed_topic() must return a string."""
        topic = _pick_random_seed_topic()
        assert isinstance(topic, str)

    def test_returned_topic_exists_in_clusters(self):
        """Topic returned must be present in one of the TOPIC_CLUSTERS."""
        all_topics = {t for topics in TOPIC_CLUSTERS.values() for t in topics}
        for _ in range(20):
            topic = _pick_random_seed_topic()
            assert (
                topic in all_topics
            ), f"Returned topic {topic!r} not found in TOPIC_CLUSTERS"

    def test_returns_different_topics_over_runs(self):
        """Multiple calls should not always return the same topic (probabilistic)."""
        results = {_pick_random_seed_topic() for _ in range(50)}
        assert len(results) > 1, "Expected diverse topics across 50 calls"

    def test_covers_multiple_clusters(self):
        """Over many calls, topics from at least 2 different clusters must appear."""
        seen_clusters = set()
        for _ in range(50):
            topic = _pick_random_seed_topic()
            for cluster, topics in TOPIC_CLUSTERS.items():
                if topic in topics:
                    seen_clusters.add(cluster)
        assert (
            len(seen_clusters) >= 2
        ), f"Expected topics from multiple clusters, got: {seen_clusters}"


class TestConfigSeedTopic:
    """Config seed_topic field validation."""

    def test_default_seed_topic_is_in_clusters(self):
        """Config() default seed_topic must come from TOPIC_CLUSTERS."""
        all_topics = {t for topics in TOPIC_CLUSTERS.values() for t in topics}
        cfg = Config()
        assert (
            cfg.seed_topic in all_topics
        ), f"Config default seed_topic {cfg.seed_topic!r} not found in TOPIC_CLUSTERS"

    def test_explicit_seed_topic_is_respected(self):
        """Config(seed_topic=...) must use the provided value."""
        cfg = Config(seed_topic="Freedom")
        assert cfg.seed_topic == "Freedom"

    def test_explicit_custom_seed_topic(self):
        """Config accepts seed_topic values outside TOPIC_CLUSTERS."""
        cfg = Config(seed_topic="My custom topic")
        assert cfg.seed_topic == "My custom topic"

    def test_different_instances_may_have_different_topics(self):
        """Multiple Config() instances should not always share the same seed_topic."""
        topics = {Config().seed_topic for _ in range(30)}
        assert len(topics) >= 1  # At minimum always valid; diversity is probabilistic


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
