from pathlib import Path

import pytest
from openpyxl import Workbook

from app.models import Workflow
from app.workflow_loader import WorkflowLoaderError, load_workflows


def create_workbook(path: Path, rows: list[tuple[object, ...]]) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    for row in rows:
        worksheet.append(row)
    workbook.save(path)


def test_loads_workflows_with_dynamic_headers_and_ignores_empty_rows(tmp_path: Path) -> None:
    workbook_path = tmp_path / "workflows.xlsx"
    create_workbook(
        workbook_path,
        [
            ("Workflow_Name", "Extra", "Workflow_ID"),
            ("First workflow", "value", "wf-1"),
            (None, None, None),
            ("Second workflow", "another", "wf-2"),
        ],
    )

    workflows = load_workflows(workbook_path)

    assert workflows == [
        Workflow("wf-1", "First workflow", {
            "Workflow_Name": "First workflow",
            "Extra": "value",
            "Workflow_ID": "wf-1",
        }),
        Workflow("wf-2", "Second workflow", {
            "Workflow_Name": "Second workflow",
            "Extra": "another",
            "Workflow_ID": "wf-2",
        }),
    ]
    assert workflows[0]["Extra"] == "value"


def test_rejects_missing_required_columns(tmp_path: Path) -> None:
    workbook_path = tmp_path / "workflows.xlsx"
    create_workbook(workbook_path, [("Workflow_ID",), ("wf-1",)])

    with pytest.raises(WorkflowLoaderError, match="missing required columns: Workflow_Name"):
        load_workflows(workbook_path)


def test_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(WorkflowLoaderError, match="file not found"):
        load_workflows(tmp_path / "missing.xlsx")


def test_rejects_duplicate_headers(tmp_path: Path) -> None:
    workbook_path = tmp_path / "workflows.xlsx"
    create_workbook(
        workbook_path,
        [("Workflow_ID", "Workflow_ID", "Workflow_Name")],
    )

    with pytest.raises(WorkflowLoaderError, match="duplicate headers"):
        load_workflows(workbook_path)
