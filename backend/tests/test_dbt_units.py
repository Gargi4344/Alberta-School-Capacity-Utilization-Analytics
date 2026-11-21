from pipeline.dbt import DBT_DIR, dbt_env, dbt_vars


def test_dbt_env_comes_from_database_url() -> None:
    env = dbt_env("postgresql+psycopg://user:p%40ss@db.example:6543/warehouse")
    assert env == {
        "ABCAP_DB_HOST": "db.example",
        "ABCAP_DB_PORT": "6543",
        "ABCAP_DB_USER": "user",
        "ABCAP_DB_PASSWORD": "p@ss",  # URL-decoded
        "ABCAP_DB_NAME": "warehouse",
    }


def test_dbt_vars_convert_percentages_to_ratios() -> None:
    assert dbt_vars(85, 100) == {"utilization_threshold": 0.85, "over_capacity_threshold": 1.0}


def test_dbt_project_is_where_the_runner_expects() -> None:
    assert (DBT_DIR / "dbt_project.yml").is_file()
    assert (DBT_DIR / "profiles.yml").is_file()
