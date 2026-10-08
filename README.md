# AI Agent Workflow Automation

## Project overview

This project is a generic AI agent workflow automation foundation. Its
assignment objective is to load workflow definitions from Excel, select the
best workflow for a natural-language request, resolve the workflow steps to
reusable tools, execute those tools against local sample data, and return a
structured execution trace and final result.

The workflow definitions remain external data rather than Python business
logic. The application currently supports workflow loading, LLM-backed or
DEMO/MOCK selection, generic step resolution, generic execution, a reusable
tool registry, local sample-data tools, and an interactive CLI.

## Architecture

```text
Application startup
    |
    v
Excel Workflow Loader
    |
    v
Loaded workflow catalog

User Request
    |
    v
Agent
    |
    v
Workflow Selector
    |
    v
Step Resolver
    |
    v
Executor
    |
    v
Tool Registry
    |
    v
Reusable Tools
    |
    v
Execution Trace / Final Result
```

The Excel loader runs at application startup and supplies the loaded workflow
catalog to the agent. The agent then orchestrates the request-time components;
it does not replace their responsibilities. The workflow selector selects a
workflow from that catalog, the resolver plans step-to-tool mappings, the
executor runs planned steps, and the `ToolRegistry` locates and invokes
registered tools.

The executor does **not** contain workflow-ID-specific branches such as
`if workflow_id == "WF001"`. Adding a workflow is intended to be a data and
tool-planning change rather than an executor rewrite.

## Workflow source

Workflows are loaded dynamically from:

```text
data/workflows.xlsx
```

The loader reads the first worksheet and its header row dynamically. It
requires `Workflow_ID` and `Workflow_Name`, preserves the other columns, and
ignores completely empty rows.

The workbook currently defines these ten workflows:

| ID | Name | Description |
|---|---|---|
| WF001 | Inventory Restock Check | Identify products below their minimum stock level and calculate reorder quantities. |
| WF002 | Product Price Validation | Match internal and vendor prices, calculate percentage differences, and flag exceptions. |
| WF003 | Vendor File Processing | Read and normalize vendor data, validate required fields, identify invalid rows, and produce a cleaned dataset. |
| WF004 | Product Description Generator | Validate supplied product attributes and generate product content fields. |
| WF005 | Customer Order Status | Find an order, retrieve its status and shipment information, and summarize it. |
| WF006 | Duplicate Product Detection | Normalize and compare catalog records to identify likely duplicate products. |
| WF007 | Marketing Campaign Brief | Validate campaign inputs and create a structured campaign brief. |
| WF008 | SEO Keyword Classification | Read keywords, classify search intent, map categories, identify priority, and report results. |
| WF009 | Employee Task Assignment | Compare task requirements with employee skills and workload, rank candidates, and summarize an assignment. |
| WF010 | Workflow Performance Report | Calculate execution metrics, analyze errors and slow steps, and produce a performance report. |

The workbook's `Trigger`, `Inputs`, `Steps`, `Decision_Logic`,
`Tools_Required`, and `Expected_Output` fields are used as workflow metadata
for selection, step resolution, execution, and reporting.

## Reusable tool layer

Tools are registered through:

```python
from app.tool_registry import ToolRegistry
from app.tools import register_default_tools

registry = register_default_tools(ToolRegistry())
```

The registry resolves tools by generic name and returns structured results or
structured errors. It has no knowledge of WF001-WF010.

Examples of reusable tools include:

- `tabular_file_reader` and `file_exporter`
- `schema_normalizer` and `record_validator`
- `record_lookup`, `shipment_lookup`, and `record_matcher`
- `text_normalizer` and `similarity_scorer`
- `numeric_calculator` and `threshold_checker`
- `capacity_checker` and `candidate_ranker`
- `text_classifier`, `text_validator`, `text_generator`, and `text_summarizer`
- `error_analyzer`, `recommendation_generator`, and `report_builder`

Deterministic operations such as arithmetic, matching, validation,
normalization, ranking, and threshold comparisons are implemented in Python.
LLM-backed text operations use the existing `LLMClient` abstraction.

## LLM and DEMO/MOCK mode

The application supports an OpenAI-compatible LLM client configured through
environment variables:

```text
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
```

Copy `.env.example` to `.env` and fill these values only when using a real
provider. Do not commit `.env` or API keys.

When the LLM configuration is unavailable, `main.py` automatically enters
clearly labeled `DEMO/MOCK` mode. Demo selection is deterministic and uses the
workflow metadata loaded from Excel. It does not require an API key and does
not change the real LLM client architecture. DEMO/MOCK text-generation,
classification, summarization, and recommendation results are deterministic
mock responses when the demo client is injected.

## Setup

Create and activate a virtual environment:

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Optional real-LLM configuration:

```powershell
Copy-Item .env.example .env
```

Edit `.env` with the provider's OpenAI-compatible endpoint, model, and API
key. A real API key is not required for local DEMO/MOCK mode.

## Run the application

```bash
python main.py
```

The CLI prompts repeatedly:

```text
Enter your workflow request (or 'exit' to quit):
```

Enter a natural-language request, or type `exit`/`quit` to stop. Every
non-empty request goes through the complete agent pipeline.

## Example requests

```text
Check today's inventory and identify products that need restocking.
```

```text
Validate the product prices against the vendor prices.
```

```text
Show me the status of order ORD1001.
```

Other examples include:

```text
Process the vendor products file and validate required fields.
Find duplicate products in the product catalog.
Generate a workflow performance report from the execution logs.
```

## CLI output

For each request, the CLI displays:

- **User Request**
- **Selected Workflow**
- **Selection Reason** and confidence
- **Execution Steps**, including each step status
- **Tools Used**
- **Decisions**, including the workflow's decision logic where applicable
- **Final Result**
- **Errors**, when present
- **Status**

The displayed steps and tools come from the actual resolver, executor,
`ToolRegistry`, and tool results. They are not a fabricated presentation
trace.

## Error and decision handling

The loader reports missing or malformed Excel files and invalid headers. The
selector validates LLM JSON, confidence, and workflow IDs. The resolver
returns structured errors for unknown or unsafe step mappings and missing
required inputs. The executor records failed steps, errors, and skipped
following steps instead of allowing one tool failure to crash the application.
The registry captures unknown-tool and tool-execution failures.

Decision logic supplied by Excel is preserved in the execution context and
applied through deterministic Python operations where the required fields and
conditions are defined. For example, inventory restocking applies
`current_stock < minimum_stock`, and price validation applies the workbook's
10% exception threshold. If the workbook lacks enough information to make a
safe mapping or calculation, the application reports an error or limitation
instead of silently guessing.

## Local sample data

Unavailable business APIs and databases are simulated with local data under:

```text
data/sample_data/
```

See [data/sample_data/README.md](data/sample_data/README.md) for each
dataset's columns, purpose, and workflow usage. No external business APIs are
called by this project.

## Adding WF011

To add WF011:

1. Add a new row to `data/workflows.xlsx`.
2. Define its `Workflow_ID` and `Workflow_Name`.
3. Define `Trigger`, `Inputs`, `Steps`, `Decision_Logic`,
   `Tools_Required`, and `Expected_Output`.
4. Reuse existing generic tools where possible.
5. Add local sample data only if the workflow needs a source not already
   represented.
6. Add or extend generic resolver/tool capabilities only when the metadata
   requires a capability that does not yet exist.

No workflow-specific executor branch should be required. The resolver must
have enough metadata to map each step safely; otherwise it returns a
structured unresolved-step error.

## Project structure

```text
.
├── app/
│   ├── __init__.py
│   ├── agent.py
│   ├── executor.py
│   ├── llm_client.py
│   ├── models.py
│   ├── step_resolver.py
│   ├── tool_registry.py
│   ├── tools/
│   │   ├── __init__.py
│   │   └── core.py
│   ├── workflow_loader.py
│   └── workflow_selector.py
├── data/
│   ├── sample_data/
│   │   ├── README.md
│   │   ├── campaign_products.csv
│   │   ├── employees.json
│   │   ├── execution_logs.json
│   │   ├── inventory.csv
│   │   ├── keywords.csv
│   │   ├── orders.json
│   │   ├── product_catalog.csv
│   │   ├── product_prices.csv
│   │   ├── shipments.json
│   │   ├── tasks.json
│   │   ├── vendor_prices.csv
│   │   └── vendor_products.csv
│   └── workflows.xlsx
├── tests/
│   ├── test_agent.py
│   ├── test_executor.py
│   ├── test_llm_client.py
│   ├── test_step_resolver.py
│   ├── test_tool_registry.py
│   ├── test_tools.py
│   ├── test_workflow_loader.py
│   └── test_workflow_selector.py
├── .env.example
├── .gitignore
├── main.py
├── README.md
└── requirements.txt
```

## Tests

Run the complete test suite:

```bash
python -m pytest -q
```

Tests use mocked LLM clients and local sample data, so they do not require an
API key or external services.

## Current limitations

- Some business formulas, ranking weights, similarity thresholds, report
  periods, and other thresholds are underspecified by the workbook.
- Local CSV/JSON sample data is used instead of real external APIs or
  databases.
- DEMO/MOCK LLM outputs are deterministic and are not equivalent to production
  model-generated content.
- The resolver uses workflow metadata and registered generic capabilities; it
  reports an error when free-form Excel text does not safely identify a tool or
  required argument.
