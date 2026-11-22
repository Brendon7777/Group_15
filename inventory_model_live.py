"""Inventory model using live stock and fixed historical demand.

Use from the website with an already-open MySQL DB-API connection:
    results = calculate_from_database(connection)
    print_summary(results)

The caller owns the connection and transaction. Call again after committed stock
changes using a fresh read transaction so the query sees current stock.
This module does not place orders, write stock or assume deliveries occurred.

Database source: resource joined with consumable_demand_history.

Database mapping:
    resource.quantity_in_stock -> A, never reduced by historical demand again
    consumable_demand_history.demand_values -> six monthly / three annual values
    resource.review_policy -> six_month or annual
    resource.unit_of_measure and resource.unit_price -> stock unit and price

History dates are inclusive. Values are consecutive and ordered oldest to newest.
The formulas and rounded z-values below are preserved from the uploaded model.
The model assumes no outstanding supplier orders or backorders. Run supplier
ordering decisions at the intended review date; live calculations are previews.
"""

import json
import math
from datetime import date, datetime, timedelta
from statistics import pstdev

service_level = 0.95
policies = {
    'six_month': {
        'title': 'Six-month consumables', 'review_interval': 6, 'lead_time': 1,
        'order_month': 'June', 'receipt_month': 'July',
    },
    'annual': {
        'title': 'Annual consumables', 'review_interval': 12, 'lead_time': 2,
        'order_month': 'November', 'receipt_month': 'January',
    },
}

MODEL_INPUT_SQL = """
SELECT r.resource_id, r.resource_name, r.grade, r.review_policy,
       r.unit_of_measure, r.unit_price, r.quantity_in_stock AS A,
       h.history_start, h.history_end, h.demand_values
FROM resource AS r
LEFT JOIN consumable_demand_history AS h
  ON h.resource_id = r.resource_id
WHERE r.review_policy IS NOT NULL
ORDER BY r.resource_id, h.history_start
"""

def average_monthly_demand(monthly_demand):
    """Calculate the mean demand in one month.

    Args:
        monthly_demand: Non-empty list of monthly quantities for one product.
    Returns:
        Unrounded monthly average, used in the six-month ordering model.
    """
    return sum(monthly_demand) / len(monthly_demand)

def demand_std_dev(monthly_demand):
    """Calculate variation between the recorded monthly demand quantities.

    Args:
        monthly_demand: Non-empty list of monthly demand quantities.
    Returns:
        Population standard deviation from pstdev. This is not rounded
        before being used to calculate safety stock.
    """
    return pstdev(monthly_demand)

def recommended_quantity(A, average, sigma, z, review_interval, lead_time):
    """Calculate the target and order for demand occurring throughout the period.

    Args:
        A: On-hand stock at review, with no outstanding orders/backorders.
        average: Mean monthly demand.
        sigma: Standard deviation of monthly demand.
        z: Normal safety factor for the selected cycle service level.
        review_interval: Months between reviews (T).
        lead_time: Months between order and receipt (L).
    Returns:
        (SS, S, quantity): Safety stock, target stock and whole-unit order.
        The protection period is T+L. SS and S retain full precision;
        the order is ceil(S-A), with a minimum of zero.
    """
    period = review_interval + lead_time
    SS = z * sigma * math.sqrt(period)
    S = average * period + SS
    quantity = max(0, math.ceil(S - A))
    return SS, S, quantity

def stockout_risk(A, average, lead_time, SS):
    """Assign a warning about stock lasting until the next delivery.

    Args:
        A: On-hand quantity at review.
        average: Mean monthly demand.
        lead_time: Months until delivery.
        SS: Safety stock calculated for the full protection period.
    Returns:
        (expected_remaining, colour, risk). Expected remaining stock is
        A-average*lead_time. Red means it is <=0; yellow means it is >0
        but <=SS; green means it is >SS. These thresholds are an illustrative
        warning rule, not probabilities. This function is not used for books.
    """
    expected_remaining = A - average * lead_time
    if expected_remaining <= 0:
        colour, risk = 'red', 'High risk'
    elif expected_remaining <= SS:
        colour, risk = 'yellow', 'Elevated risk'
    else:
        colour, risk = 'green', 'Low risk'
    return expected_remaining, colour, risk

def average_annual_demand(annual_demand):
    """Estimate the quantity required for one annual book distribution.

    Args:
        annual_demand: Three annual issue totals, ordered oldest to latest.
    Returns:
        Unrounded mean issue quantity in books. This is a quantity for one
        distribution, not a continuous monthly demand rate.
    """
    return sum(annual_demand) / len(annual_demand)

def annual_demand_std_dev(annual_demand):
    """Calculate variation between annual book issue totals.

    Args:
        annual_demand: Non-empty list of historical annual issue quantities.
    Returns:
        Population standard deviation of issue quantity, in books.
        Three observations provide only a limited estimate of variation.
    """
    return pstdev(annual_demand)

def annual_recommended_quantity(A, average, sigma, z):
    # One annual distribution, supplied before the issue date.
    """Calculate an order covering the next single annual book issue.

    Args:
        A: Usable books remaining at the November review.
        average: Forecast quantity for one annual distribution.
        sigma: Standard deviation of annual distribution quantity.
        z: Normal safety factor for the selected service level.
    Returns:
        (SS, S, quantity), using SS=z*sigma and S=average+SS.
        Each receipt is assumed to precede its January distribution.
        Therefore no T+L rate multiplier is used. The whole-unit order
        is ceil(S-A), with a minimum of zero.
    """
    SS = z * sigma
    S = average + SS
    quantity = max(0, math.ceil(S - A))
    return SS, S, quantity

def get_z_value(service_level):
    """Look up the normal safety factor for a supported service level.

    Args:
        service_level: One of 0.90, 0.95, 0.97 or 0.99.
    Returns:
        Corresponding rounded z-value, such as 1.65 for 0.95.
    Raises:
        KeyError: If the supplied service level is not in the lookup.
    """
    service_level_z = {0.90: 1.28, 0.95: 1.65, 0.97: 1.88, 0.99: 2.33}
    return service_level_z[service_level]

def order_cost(quantity, unit_price):
    """Calculate purchasing cost, without extra freight or taxes.

    Args:
        quantity: Recommended whole-unit order quantity.
        unit_price: Rand price per pack, roll or book, matching stock units.
    Returns:
        Quantity times unit price, rounded to two decimal places.
    """
    return round(quantity * unit_price, 2)

def _number(value, label, whole=False):
    if value is None or isinstance(value, bool):
        raise ValueError(f"{label}: a nonnegative number is required")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label}: invalid number {value!r}") from exc
    if not math.isfinite(number) or number < 0 or (whole and not number.is_integer()):
        raise ValueError(f"{label}: expected a finite nonnegative {'integer' if whole else 'number'}")
    return int(number) if whole else number


def _date(value, label):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}: a valid date is required") from exc


def products_from_rows(rows):
    """Convert joined database rows into inputs keyed by resource ID.

    Each row is a mapping containing the columns selected by MODEL_INPUT_SQL.
    Missing histories and prices raise errors rather than silently omitting items.
    Both JSON text/bytes and driver-decoded Python lists are accepted.
    """
    products = {}
    for row in rows:
        resource_id = _number(row['resource_id'], 'resource_id', whole=True)
        label = f"Resource {resource_id} ({row['resource_name']})"
        if resource_id in products:
            raise ValueError(f"{label}: duplicate history row")
        policy = row['review_policy']
        if policy not in policies:
            raise ValueError(f"{label}: unsupported review_policy {policy!r}")
        raw = row['demand_values']
        if isinstance(raw, (str, bytes, bytearray)):
            try:
                history = json.loads(raw)
            except (ValueError, UnicodeError) as exc:
                raise ValueError(f"{label}: invalid demand JSON") from exc
        else:
            history = raw
        count = 6 if policy == 'six_month' else 3
        if not isinstance(history, list) or len(history) != count:
            raise ValueError(f"{label}: expected {count} historical quantities")
        if any(not isinstance(v, (int, float)) or isinstance(v, bool) for v in history):
            raise ValueError(f"{label}: historical quantities must be JSON numbers")
        history = [_number(v, label + ' demand', whole=True) for v in history]
        start = _date(row['history_start'], label + ' history_start')
        end = _date(row['history_end'], label + ' history_end')
        months = 6 if policy == 'six_month' else 36
        month_index = start.year * 12 + start.month - 1 + months
        expected_end = date(month_index // 12, month_index % 12 + 1, 1) - timedelta(days=1)
        if start.day != 1 or end != expected_end:
            raise ValueError(f"{label}: dates must span {months} complete months (inclusive)")
        unit = row['unit_of_measure']
        if not isinstance(unit, str) or not unit.strip():
            raise ValueError(f"{label}: stock unit is required")
        products[resource_id] = {
            'resource_name': row['resource_name'], 'grade': row.get('grade'),
            'policy': policy, 'unit': unit,
            'unit_price': _number(row['unit_price'], label + ' unit_price'),
            'A': _number(row['A'], label + ' A', whole=True),
            'history_start': start, 'history_end': end,
            'monthly_demand' if policy == 'six_month' else 'annual_demand': history,
        }
    return products


def load_products(connection):
    """Read current stock and fixed histories with one query; never writes data."""
    cursor = connection.cursor()
    try:
        cursor.execute(MODEL_INPUT_SQL)
        columns = [column[0] for column in cursor.description]
        rows = [row if hasattr(row, 'keys') else dict(zip(columns, row))
                for row in cursor.fetchall()]
    finally:
        cursor.close()
    return products_from_rows(rows)


def calculate_results(product_inputs, selected_service_level=service_level):
    """Run the original formulas using an explicit live A for every resource.

    product_inputs is the ID-keyed dictionary returned by load_products() or
    products_from_rows(). There are no opening-stock, receipt or carry-over inputs.
    """
    z = get_z_value(selected_service_level)
    results = {}
    for resource_id, inputs in product_inputs.items():
        policy_key = inputs['policy']
        policy = policies[policy_key]
        A = _number(inputs['A'], f'Resource {resource_id} A', whole=True)
        if policy_key == 'annual':
            history = inputs['annual_demand']
            average = average_annual_demand(history)
            sigma = annual_demand_std_dev(history)
            SS, S, quantity = annual_recommended_quantity(A, average, sigma, z)
            expected_remaining, colour, risk = None, None, None
        else:
            history = inputs['monthly_demand']
            average = average_monthly_demand(history)
            sigma = demand_std_dev(history)
            SS, S, quantity = recommended_quantity(
                A, average, sigma, z, policy['review_interval'], policy['lead_time'])
            expected_remaining, colour, risk = stockout_risk(
                A, average, policy['lead_time'], SS)
        price = _number(inputs['unit_price'], f'Resource {resource_id} unit_price')
        results[resource_id] = {
            'resource_id': resource_id, 'resource_name': inputs['resource_name'],
            'grade': inputs.get('grade'), 'policy': policy_key, 'unit': inputs['unit'],
            'history_start': inputs['history_start'], 'history_end': inputs['history_end'],
            'history': list(history), 'historical_demand_total': sum(history),
            'average': average, 'sigma': sigma, 'A': A, 'SS': SS, 'S': S,
            'quantity': quantity, 'unit_price': price, 'cost': order_cost(quantity, price),
            'expected_remaining': expected_remaining, 'colour': colour, 'risk': risk,
        }
    return results


def calculate_from_database(connection, selected_service_level=service_level):
    """Website entry point: reload live stock, then calculate all consumables."""
    return calculate_results(load_products(connection), selected_service_level)


def print_summary(results):
    for key, policy in policies.items():
        print(f"\n{policy['title']} | order: {policy['order_month']}; receipt: {policy['receipt_month']}")
        for output in results.values():
            if output['policy'] != key:
                continue
            print(f"\n{output['resource_id']}: {output['resource_name']} ({output['unit']})")
            print(f"  Historical window: {output['history_start']} to {output['history_end']}")
            print(f"  Historical quantities: {output['history']}")
            print(f"  Average demand: {output['average']:.2f}")
            print(f"  Current on hand (A): {output['A']}")
            print(f"  Safety stock (rounded up): {math.ceil(output['SS'])}")
            print(f"  Target stock (rounded up): {math.ceil(output['S'])}")
            print(f"  Recommended order: {output['quantity']}")
            print(f"  Unit price: R{output['unit_price']:.2f}; purchasing cost: R{output['cost']:,.2f}")
            if key == 'six_month':
                print(f"  Stock warning before delivery: {output['risk']} ({output['colour']})")
