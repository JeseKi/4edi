from __future__ import annotations

import pytest

from src.server.platform.features import resolve_features, task_definitions_for


def test_default_template_features_have_the_expected_task_surface() -> None:
    features = resolve_features(["auth", "admin", "files", "example"], app_env="dev")

    assert [feature.name for feature in features] == ["auth", "admin", "files", "example"]
    assert {definition.name for definition in task_definitions_for(features)} == {
        "files.expire_pending_upload",
        "files.delete_object",
        "example.async_task.run",
    }


def test_all_expands_to_non_development_features_outside_dev() -> None:
    features = resolve_features(["all"], app_env="test")

    assert {feature.name for feature in features} == {
        "admin",
        "audit",
        "auth",
        "example",
        "files",
        "frontend-error-reporting",
        "oauth-login",
        "oauth-provider",
        "notifications",
        "mall",
    }


def test_feature_dependencies_are_validated_before_app_start() -> None:
    with pytest.raises(ValueError, match="缺少依赖"):
        resolve_features(["files"], app_env="dev")
    with pytest.raises(ValueError, match="未知功能包"):
        resolve_features(["not-a-feature"], app_env="dev")
    with pytest.raises(ValueError, match="仅允许在 dev"):
        resolve_features(["dev-providers"], app_env="test")


def test_task_definitions_come_from_enabled_features_only() -> None:
    features = resolve_features(["auth", "files", "example"], app_env="dev")

    assert {definition.name for definition in task_definitions_for(features)} == {
        "files.expire_pending_upload",
        "files.delete_object",
        "example.async_task.run",
    }


def test_frontend_config_exposes_the_resolved_web_surface(test_client) -> None:
    response = test_client.get("/api/frontend-config")

    assert response.status_code == 200
    assert set(response.json()["features"]) == {
        "admin",
        "audit",
        "auth",
        "example",
        "files",
        "frontend-error-reporting",
        "oauth-login",
        "oauth-provider",
        "notifications",
        "mall",
    }
