"""Custom schema generator configuration."""

from drf_spectacular.generators import SchemaGenerator


class CanonicalSchemaGenerator(SchemaGenerator):
    """Generate docs from the canonical schema URLConf by default."""

    def __init__(self, *args, **kwargs):
        if not kwargs.get("urlconf"):
            kwargs["urlconf"] = "config.schema_urls"
        super().__init__(*args, **kwargs)
