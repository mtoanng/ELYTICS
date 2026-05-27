import backend.services.sql as sql_service


def test_resolve_query_source_uses_view_when_local_sql_disabled(monkeypatch):
    monkeypatch.setattr(sql_service, "LOCAL_SQL", False)

    query_source, cache_source = sql_service.resolve_query_source(
        space="sherlock",
        data_kind="data",
        table_name="ccm",
    )

    assert query_source == cache_source
    assert cache_source.endswith("holmes_sherlock_ccm_data_view")


def test_resolve_query_source_uses_local_sql_when_enabled(monkeypatch):
    monkeypatch.setattr(sql_service, "LOCAL_SQL", True)
    monkeypatch.setattr(sql_service, "read_local_sql", lambda _: "SELECT 1 AS x")

    query_source, cache_source = sql_service.resolve_query_source(
        space="sherlock",
        data_kind="metadata",
        table_name="polcurve",
    )

    assert query_source == "(SELECT 1 AS x) AS local_source"
    assert cache_source.endswith("holmes_sherlock_polcurve_meta_view")
