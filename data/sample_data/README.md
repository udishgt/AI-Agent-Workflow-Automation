# Sample data

These small local datasets simulate the unavailable business files, APIs, and
databases referenced by the Excel workflows. They are deliberately synthetic.

| Dataset | Columns | Used by |
|---|---|---|
| `inventory.csv` | `sku`, `product_name`, `current_stock`, `minimum_stock`, `unit_price` | WF001 |
| `product_prices.csv` | `sku`, `product_name`, `internal_price` | WF002 |
| `vendor_prices.csv` | `sku`, `vendor_price` | WF002 |
| `vendor_products.csv` | `sku`, `product_name`, `category`, `price` | WF003 |
| `orders.json` | `order_id`, `customer_email`, `status`, `items` | WF005 |
| `shipments.json` | `order_id`, `shipment_status`, `tracking_number` | WF005 |
| `product_catalog.csv` | `sku`, `product_name`, `category`, `material`, `color` | WF006 |
| `campaign_products.csv` | `sku`, `product_name`, `category`, `price` | WF007 |
| `keywords.csv` | `keyword`, `category` | WF008 |
| `employees.json` | `employee_id`, `name`, `skills`, `workload`, `capacity` | WF009 |
| `tasks.json` | `task_id`, `description`, `required_skill`, `priority`, `deadline` | WF009 |
| `execution_logs.json` | `workflow_id`, `status`, `duration_seconds`, `error`, `step` | WF010 |

Assumptions are limited to practical file formats and column types because the
Excel workbook does not define source schemas, database connections, formulas
for reorder quantities, ranking weights, or report periods.
