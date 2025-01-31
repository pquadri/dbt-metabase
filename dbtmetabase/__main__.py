import functools
import logging
from pathlib import Path
from typing import Callable, Optional, Sequence

import click
import yaml
from typing_extensions import cast

from ._format import click_list_option_kwargs, setup_logging
from .core import DbtMetabase
from .core_exposures import ExposuresExtractorMixin
from .core_models import ModelsExporterMixin
from .interface import Filter


@click.group()
@click.version_option(package_name="dbt-metabase")
@click.option(
    "--config-path",
    default="~/.dbt-metabase/config.yml",
    show_default=True,
    type=click.Path(),
    help="Path to config.yml file with default values.",
)
@click.pass_context
def cli(ctx: click.Context, config_path: str):
    group = cast(click.Group, ctx.command)

    config_path_expanded = Path(config_path).expanduser()
    if config_path_expanded.exists():
        with open(config_path_expanded, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f).get("config", {})
            # Propagate root configs to all commands
            ctx.default_map = {command: config for command in group.commands}


def _add_setup(func: Callable) -> Callable:
    """Add common options and initialize core."""

    @click.option(
        "--manifest-path",
        envvar="MANIFEST_PATH",
        show_envvar=True,
        required=True,
        type=click.Path(exists=True, dir_okay=False),
        help="Path to dbt manifest.json, usually in target/ directory after compilation.",
    )
    @click.option(
        "--metabase-url",
        metavar="URL",
        envvar="METABASE_URL",
        show_envvar=True,
        required=True,
        type=click.STRING,
        help="Metabase URL, e.g. 'https://metabase.example.com'.",
    )
    @click.option(
        "--metabase-username",
        metavar="USERNAME",
        envvar="METABASE_USERNAME",
        show_envvar=True,
        type=click.STRING,
        help="Metabase username (required unless providing session ID).",
    )
    @click.option(
        "--metabase-password",
        metavar="PASSWORD",
        envvar="METABASE_PASSWORD",
        show_envvar=True,
        type=click.STRING,
        help="Metabase password (required unless providing session ID).",
    )
    @click.option(
        "--metabase-session-id",
        metavar="TOKEN",
        envvar="METABASE_SESSION_ID",
        show_envvar=True,
        type=click.STRING,
        help="Metabase session ID (alternative to username/password).",
    )
    @click.option(
        "--skip-verify",
        envvar="SKIP_VERIFY",
        show_envvar=True,
        help="Skip TLS certificate verification (not recommended).",
    )
    @click.option(
        "--cert",
        metavar="CERT",
        envvar="CERT",
        show_envvar=True,
        type=click.Path(exists=True, dir_okay=False),
        help="Path to TLS certificate bundle.",
    )
    @click.option(
        "--http-timeout",
        metavar="SECS",
        envvar="HTTP_TIMEOUT",
        show_envvar=True,
        type=click.INT,
        default=DbtMetabase.DEFAULT_HTTP_TIMEOUT,
        show_default=True,
        help="HTTP timeout in seconds.",
    )
    @click.option(
        "-v",
        "--verbose",
        is_flag=True,
        help="Enable verbose logging.",
    )
    @functools.wraps(func)
    def wrapper(
        manifest_path: str,
        metabase_url: str,
        metabase_username: str,
        metabase_password: str,
        metabase_session_id: Optional[str],
        skip_verify: bool,
        cert: Optional[str],
        http_timeout: int,
        verbose: bool,
        **kwargs,
    ):
        setup_logging(
            level=logging.DEBUG if verbose else logging.INFO,
            path=Path.home().absolute() / ".dbt-metabase" / "logs" / "dbtmetabase.log",
        )

        return func(
            core=DbtMetabase(
                manifest_path=manifest_path,
                metabase_url=metabase_url,
                metabase_username=metabase_username,
                metabase_password=metabase_password,
                metabase_session_id=metabase_session_id,
                skip_verify=skip_verify,
                cert=cert,
                http_timeout=http_timeout,
            ),
            **kwargs,
        )

    return wrapper


@cli.command(help="Export dbt models to Metabase.")
@_add_setup
@click.option(
    "--metabase-database",
    metavar="METABASE_DATABASE",
    envvar="METABASE_DATABASE",
    show_envvar=True,
    required=True,
    type=click.STRING,
    help="Target database in Metabase.",
)
@click.option(
    "--include-databases",
    metavar="DATABASES",
    envvar="INCLUDE_DATABASES",
    show_envvar=True,
    **click_list_option_kwargs(),
    help="Only include certain dbt databases.",
)
@click.option(
    "--exclude-databases",
    metavar="DATABASES",
    envvar="EXCLUDE_DATABASES",
    show_envvar=True,
    **click_list_option_kwargs(),
    help="Exclude certain dbt databases.",
)
@click.option(
    "--include-schemas",
    metavar="SCHEMAS",
    envvar="INCLUDE_SCHEMAS",
    show_envvar=True,
    **click_list_option_kwargs(),
    help="Only include certain dbt schemas.",
)
@click.option(
    "--exclude-schemas",
    metavar="SCHEMAS",
    envvar="EXCLUDE_SCHEMAS",
    show_envvar=True,
    **click_list_option_kwargs(),
    help="Exclude certain dbt schemas.",
)
@click.option(
    "--include-models",
    metavar="MODELS",
    envvar="INCLUDE_MODELS",
    show_envvar=True,
    **click_list_option_kwargs(),
    help="Only include certain dbt models.",
)
@click.option(
    "--exclude-models",
    metavar="MODELS",
    envvar="EXCLUDE_MODELS",
    show_envvar=True,
    **click_list_option_kwargs(),
    help="Exclude certain dbt models.",
)
@click.option(
    "--sync-timeout",
    metavar="SECS",
    envvar="SYNC_TIMEOUT",
    show_envvar=True,
    default=ModelsExporterMixin.DEFAULT_SYNC_TIMEOUT,
    type=click.INT,
    help="Number of seconds to wait until Metabase schema matches the dbt project. To skip synchronization, set timeout to 0.",
)
@click.option(
    "--skip-sources",
    envvar="SKIP_SOURCES",
    show_envvar=True,
    is_flag=True,
    help="Exclude dbt sources from export.",
)
@click.option(
    "--append-tags",
    envvar="APPEND_TAGS",
    show_envvar=True,
    is_flag=True,
    help="Append dbt tags to table descriptions.",
)
@click.option(
    "--docs-url",
    metavar="URL",
    envvar="DOCS_URL",
    show_envvar=True,
    type=click.STRING,
    help="URL for dbt docs hosting, to append model links to table descriptions.",
)
def models(
    metabase_database: str,
    include_databases: Optional[Sequence[str]],
    exclude_databases: Optional[Sequence[str]],
    include_schemas: Optional[Sequence[str]],
    exclude_schemas: Optional[Sequence[str]],
    include_models: Optional[Sequence[str]],
    exclude_models: Optional[Sequence[str]],
    skip_sources: bool,
    sync_timeout: int,
    append_tags: bool,
    docs_url: Optional[str],
    core: DbtMetabase,
):
    core.export_models(
        metabase_database=metabase_database,
        database_filter=Filter(include=include_databases, exclude=exclude_databases),
        schema_filter=Filter(include=include_schemas, exclude=exclude_schemas),
        model_filter=Filter(include=include_models, exclude=exclude_models),
        skip_sources=skip_sources,
        sync_timeout=sync_timeout,
        append_tags=append_tags,
        docs_url=docs_url,
    )


@cli.command(help="Extract dbt exposures from Metabase.")
@_add_setup
@click.option(
    "--output-path",
    envvar="OUTPUT_PATH",
    show_envvar=True,
    type=click.Path(exists=True, file_okay=False),
    default=ExposuresExtractorMixin.DEFAULT_OUTPUT_PATH,
    show_default=True,
    help="Output path for exposure YAML files.",
)
@click.option(
    "--output-grouping",
    envvar="OUTPUT_GROUPING",
    show_envvar=True,
    type=click.Choice(["collection", "type"]),
    help="Grouping key for exposure YAML files.",
)
@click.option(
    "--include-collections",
    metavar="COLLECTIONS",
    envvar="INCLUDE_COLLECTIONS",
    show_envvar=True,
    **click_list_option_kwargs(),
    help="Only include certain Metabase collections.",
)
@click.option(
    "--exclude-collections",
    metavar="COLLECTIONS",
    envvar="EXCLUDE_COLLECTIONS",
    show_envvar=True,
    **click_list_option_kwargs(),
    help="Exclude certain Metabase collections.",
)
@click.option(
    "--allow-personal-collections",
    envvar="ALLOW_PERSONAL_COLLECTIONS",
    show_envvar=True,
    is_flag=True,
    help="Include personal Metabase collections.",
)
def exposures(
    output_path: str,
    output_grouping: Optional[str],
    include_collections: Optional[Sequence[str]],
    exclude_collections: Optional[Sequence[str]],
    allow_personal_collections: bool,
    core: DbtMetabase,
):
    core.extract_exposures(
        output_path=output_path,
        output_grouping=output_grouping,
        collection_filter=Filter(
            include=include_collections,
            exclude=exclude_collections,
        ),
        allow_personal_collections=allow_personal_collections,
    )


if __name__ == "__main__":
    # Executed when running locally via python3 -m dbtmetabase
    cli()  # pylint: disable=no-value-for-parameter
