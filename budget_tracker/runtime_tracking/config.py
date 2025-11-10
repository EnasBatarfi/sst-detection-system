from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional, Set

import json
import os


@dataclass
class FieldConfig:
    category: str
    description: str
    pii: bool = True
    owner_attribute: Optional[str] = None  # attribute on SQLAlchemy model representing the owner


@dataclass
class ModelConfig:
    fields: Dict[str, FieldConfig] = field(default_factory=dict)

    def tracked_fields(self) -> Iterable[str]:
        return self.fields.keys()


@dataclass
class InputFieldConfig:
    category: str
    description: str
    pii: bool = True


@dataclass
class InstrumentationConfig:
    tracked_models: Dict[str, ModelConfig] = field(default_factory=dict)
    input_fields: Dict[str, InputFieldConfig] = field(default_factory=dict)
    ignored_hosts: Set[str] = field(default_factory=set)
    storage_path: Path = Path("runtime_provenance.db")
    audit_token: Optional[str] = None

    @staticmethod
    def default() -> "InstrumentationConfig":
        return InstrumentationConfig(
            tracked_models={
                "User": ModelConfig(
                    fields={
                        "email": FieldConfig(
                            category="contact.email",
                            description="User email address",
                            owner_attribute="email",
                        ),
                        "name": FieldConfig(
                            category="personal.name",
                            description="Account holder legal name",
                            owner_attribute="email",
                        ),
                        "birthday": FieldConfig(
                            category="personal.birthdate",
                            description="Account holder birth date",
                            owner_attribute="email",
                        ),
                        "income": FieldConfig(
                            category="financial.income",
                            description="Monthly income declared by the user",
                            owner_attribute="email",
                        ),
                        "currency": FieldConfig(
                            category="financial.currency",
                            description="Preferred currency",
                            owner_attribute="email",
                            pii=False,
                        ),
                        "gender": FieldConfig(
                            category="personal.gender",
                            description="Self-declared gender",
                            owner_attribute="email",
                        ),
                        "goals": FieldConfig(
                            category="financial.goal",
                            description="Custom budgeting goals",
                            owner_attribute="email",
                        ),
                    }
                ),
                "Expense": ModelConfig(
                    fields={
                        "amount": FieldConfig(
                            category="financial.transaction_amount",
                            description="Expense amount",
                            owner_attribute="user_id",
                        ),
                        "category": FieldConfig(
                            category="financial.transaction_category",
                            description="Expense category",
                            owner_attribute="user_id",
                            pii=False,
                        ),
                        "description": FieldConfig(
                            category="financial.transaction_description",
                            description="Free-form description",
                            owner_attribute="user_id",
                        ),
                        "date": FieldConfig(
                            category="financial.transaction_date",
                            description="Expense date",
                            owner_attribute="user_id",
                        ),
                    }
                ),
            },
            input_fields={
                "email": InputFieldConfig(category="contact.email", description="Email address"),
                "name": InputFieldConfig(category="personal.name", description="Person name"),
                "password": InputFieldConfig(category="security.credential", description="Password", pii=True),
                "birthday": InputFieldConfig(category="personal.birthdate", description="Birth date"),
                "gender": InputFieldConfig(category="personal.gender", description="Gender"),
                "income": InputFieldConfig(category="financial.income", description="Declared income"),
                "currency": InputFieldConfig(category="financial.currency", description="Currency", pii=False),
                "budget_style": InputFieldConfig(category="financial.preference", description="Budget preference", pii=False),
                "goals": InputFieldConfig(category="financial.goal", description="Financial goals"),
                "week_start": InputFieldConfig(category="preference.weekday", description="Week start", pii=False),
            },
            ignored_hosts=set(),
            storage_path=Path("runtime_provenance.db"),
            audit_token=os.getenv("RUNTIME_TRACKING_AUDIT_TOKEN")
            if "RUNTIME_TRACKING_AUDIT_TOKEN" in os.environ
            else None,
        )


def load_config(path: Path) -> InstrumentationConfig:
    with path.open("r", encoding="utf-8") as fh:
        raw = fh.read()

    if path.suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "PyYAML is required to load YAML runtime tracking config. Install `pyyaml`."
            ) from exc
        data = yaml.safe_load(raw)
    else:
        data = json.loads(raw)

    return parse_config(data, base_path=path.parent)


def parse_config(data: dict, base_path: Path) -> InstrumentationConfig:
    config = InstrumentationConfig.default()

    if "storage_path" in data:
        config.storage_path = (base_path / data["storage_path"]).expanduser().resolve()

    if "audit_token" in data:
        config.audit_token = data["audit_token"]

    if "ignored_hosts" in data:
        config.ignored_hosts = set(data["ignored_hosts"])

    if "input_fields" in data:
        config.input_fields = {
            key: InputFieldConfig(**value) for key, value in data["input_fields"].items()
        }

    if "tracked_models" in data:
        model_map: Dict[str, ModelConfig] = {}
        for model_name, model_data in data["tracked_models"].items():
            fields = {
                field_name: FieldConfig(**field_conf)
                for field_name, field_conf in model_data.get("fields", {}).items()
            }
            model_map[model_name] = ModelConfig(fields=fields)
        config.tracked_models = model_map

    return config
