from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

from apps.core.encryption import get_encrypted_model_fields, reencrypt_queryset


class Command(BaseCommand):
    help = (
        "Re-encrypt encrypted model fields using the currently configured "
        "encryption key version."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            action="append",
            dest="models",
            help="Optional app_label.ModelName target. Can be passed multiple times.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Queryset iteration batch size.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be re-encrypted without saving changes.",
        )

    def handle(self, *args, **options):
        model_specs = options["models"] or []
        batch_size = int(options["batch_size"] or 100)
        dry_run = bool(options["dry_run"])

        model_classes = self._resolve_models(model_specs)
        total_models = 0
        total_rows = 0

        for model_class in model_classes:
            encrypted_fields = get_encrypted_model_fields(model_class)
            if not encrypted_fields:
                continue

            queryset = model_class._default_manager.all()
            row_count = queryset.count()
            total_models += 1
            total_rows += row_count

            field_names = ", ".join(field.name for field in encrypted_fields)
            self.stdout.write(
                f"{model_class._meta.label}: {row_count} rows, encrypted fields [{field_names}]"
            )

            if dry_run or row_count == 0:
                continue

            updated = reencrypt_queryset(queryset, batch_size=batch_size)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Re-encrypted {updated} rows for {model_class._meta.label}"
                )
            )

        if total_models == 0:
            self.stdout.write("No encrypted models matched the selection.")
            return

        summary = (
            f"Processed {total_models} model(s) covering {total_rows} row(s)."
        )
        if dry_run:
            self.stdout.write(self.style.WARNING(f"Dry run complete. {summary}"))
        else:
            self.stdout.write(self.style.SUCCESS(summary))

    def _resolve_models(self, model_specs):
        if not model_specs:
            return [model for model in apps.get_models() if get_encrypted_model_fields(model)]

        resolved = []
        for spec in model_specs:
            if "." not in spec:
                raise CommandError(
                    f"Invalid model spec '{spec}'. Use app_label.ModelName."
                )
            app_label, model_name = spec.split(".", 1)
            model_class = apps.get_model(app_label, model_name)
            if model_class is None:
                raise CommandError(f"Unknown model '{spec}'.")
            resolved.append(model_class)
        return resolved
