"""
MODEL APPROACH AND ASSUMPTIONS

1. Both groups use a fixed-interval (periodic-review, order-up-to) policy.
   Reviews occur at fixed times; the quantity ordered varies with demand
   and the stock remaining. The review interval(T) follows the school's assumed ordering policy:
   six months for Paper/Sellotape and twelve months for activity books.

2. Paper and Sellotape are used throughout the period. Monthly demand varies,
   but its mean and variation are assumed stable, and months independent.
   Exam peaks and seasonality are not modelled separately.
   SS = z * monthly_sigma * sqrt(T + L)
   S = average_monthly_demand * (T + L) + SS
   For T=6 and L=1 month, the protection period is seven months.

3. Activity books have one January distribution and no further issues
   between distributions. Orders are placed every November and arrive in
   January before distribution. The stock cycle is December-November.
   Only one annual distribution occurs before the following replenishment.
   SS = z * annual_sigma
   S = average_annual_issue_quantity + SS
   The mean and standard deviation are in books, not books/year rates.
   No 14/12 multiplier is used. Lead time determines the ordering schedule.
   This is our application of the periodic-review approach to that schedule.

   Reference: Rossetti, M. D., Analysis of Inventory Systems, Chapter 8,
   Section 8.13, When Review Is Periodic.
   https://rossetti.github.io/RossettiInventoryBook/08-Chapter8.html
   The source supports the general method; the single January distribution
   is our school-specific assumption, not a case taken from the source.

DEMAND, SERVICE LEVEL AND DELIVERY

4. A normal approximation is assumed for protection-period demand for
   Paper/Sellotape and for the annual issue quantity for books. Normality
   has not been verified from the illustrative records.

5. The target cycle service level is 95%, using z=1.65. This is a target
   probability of avoiding a stockout, not a verified service guarantee.

6. Lead times are constant: one calendar month for Paper/Sellotape and two
   for books. June orders arrive in July; November book orders arrive in
   January before distribution. Suppliers deliver the full order quantity.

7.  The model uses demand recorded in each of the six months of the first 
    half of the year (January to June) for Paper and Sellotape, and annual 
    demand recorded over the past three years for activity books, to 
    calculate average demand and standard deviation.

8.  The latest year’s distribution demand is based on one activity book per 
    learner: 144 books for Grade 2 (4 classes × 36 learners) and 160 books 
    for Grade 3 (4 classes × 40 learners). These are demand quantities; 
    the model calculates the recommended order quantities separately.

STOCK RECORDS AND CARRY-OVER

9.  Paper is counted and priced per pack, Sellotape per roll, 
    and activity books per book.

10. Initial opening stock is 2 per product. Initial receipts are 100 packs,
    100 rolls, 144 Grade 2 books and 160 Grade 3 books. They represent
    earlier orders; no earlier calculated results are available initially.

11. Orders are assumed to be received in full, with no damaged or missing items 
    and no items returned to the supplier. All recorded demand is assumed to 
    have been met. Use all six months demand for consumables, only the 
    latest annual total for books.

12. Each cycle’s closing stock (A) becomes the next cycle’s opening stock, 
    and its order quantity becomes the stock received in the next cycle. 
    For activity books, November’s closing stock becomes December’s opening stock. 
    Fewer than 5 books are expected to remain, but the model does not enforce this 
    limit.

PRICES AND OUTPUTS

13. Unit prices are assumed constant: Paper R140 per pack, Sellotape R20 per roll, and 
    activity books R50 per book. The model focuses on the purchasing budget, 
    calculated as order quantity × unit price. 
    Holding and ordering costs are excluded because the review 
    intervals follow the school’s ordering policy. No quantity discounts, 
    additional delivery charges or taxes are included. The school is assumed to 
    have enough space to store the ordered quantities.
    
14. Calculations retain precision. Display averages to the nearest unit,
    SS and S rounded up, and money to two decimals. Orders are rounded up
    and cannot be negative. Negative calculated A would violate assumption 11.

15. Paper/Sellotape risk colours are qualitative warnings, not probabilities.
    They are not applied to the once-a-year book distribution.
    
16. Running this file prints four summaries and regenerates the HTML page.
    A new cycle needs new demand records and explicit previous_results.
    There is no database or automatic carry-over between separate runs.
"""

import math
from statistics import pstdev
from pathlib import Path
from html import escape

# monthly consumables
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

def stock_available(opening_stock, stock_received, monthly_demand):
    # Assumes all recorded demand was fulfilled.
    """Calculate the stock left at the six-month review.

    Args:
        opening_stock: Quantity carried into the start of this cycle.
        stock_received: Total quantity actually received during this cycle.
        monthly_demand: Quantities issued in the same six-month cycle.
    Returns:
        A: Opening stock plus receipts minus the sum of actual demand.
        A represents physical stock under the fulfilled-demand assumption.
    """
    A = opening_stock + stock_received - sum(monthly_demand)
    return A

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

#annual consumables

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

def annual_stock_available(opening_stock, stock_received, actual_annual_demand):
    """Calculate book stock remaining at the November review.

    Args:
        opening_stock: Stock at the start of December.
        stock_received: Full receipt during this December-November cycle.
        actual_annual_demand: Latest cycle's actual book issue quantity.
    Returns:
        Closing A in books. Only this cycle's demand is subtracted;
        the three-year sum and historical mean are not used here.
    """
    A = opening_stock + stock_received - actual_annual_demand
    return A 

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


# both models
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

def carry_over(previous_A, previous_quantity):
    """Prepare one product's inputs for its next cycle.

    Args:
        previous_A: This product's previous closing on-hand quantity.
        previous_quantity: Its previous recommended order quantity.
    Returns:
        (opening_stock, stock_received). Full receipt of the previous
        order during the new cycle is assumed. This function does not
        save state or advance the calendar automatically.
    """
    opening_stock = previous_A
    stock_received = previous_quantity
    return opening_stock, stock_received

# All time inputs are in months. Each policy has its own review and lead time.
service_level = 0.95
policies = {
    'six_month': {
        'title': 'Six-month review: Paper and Sellotape',
        'period': 'January-June', 'review_interval': 6, 'lead_time': 1,
        'order_month': 'June', 'receipt_month': 'July'
    },
    'annual': {
        'title': 'Annual review: Activity books',
        'period': 'December-November', 'review_interval': 12, 'lead_time': 2,
        'order_month': 'November', 'receipt_month': 'January'
    }
}

products = {
    'Paper': {
        'policy': 'six_month', 'unit': 'packs',
        'monthly_demand': [10, 9, 20, 10, 15, 20],
        'A_initial': 2, 'received_initial': 100, 'unit_price': 140.00
    },
    'Sellotape': {
        'policy': 'six_month', 'unit': 'rolls',
        'monthly_demand': [20, 25, 10, 8, 7, 10],
        'A_initial': 2, 'received_initial': 100, 'unit_price': 20.00
    },
    'Grade 2 activity books': {
        'policy': 'annual', 'unit': 'books',
        'classrooms': 4, 'learners_per_class': 36,
        # Oldest to latest annual demand record.
        'annual_demand': [136, 140, 144],
        'A_initial': 2, 'received_initial': 144, 'unit_price': 50.00
    },
    'Grade 3 activity books': {
        'policy': 'annual', 'unit': 'books',
        'classrooms': 4, 'learners_per_class': 40,
        'annual_demand': [152, 156, 160],
        'A_initial': 2, 'received_initial': 160, 'unit_price': 50.00
    }
}


def calculate_results(product_inputs=None, previous_results=None):
    """Run the appropriate model for each product and collect its answers.

    Args:
        product_inputs: Product dictionary; None selects the global products.
        previous_results: Previous answers keyed by product name. None uses
            initial inputs; supplying answers activates carry-over.
    Returns:
        A dictionary keyed by product name, containing demand statistics,
        stock quantities, order quantity, unit price, cost and risk fields.
        Annual products use the latest annual total for A and all annual
        totals for forecasting. Other demo products use monthly records.
        Annual risk fields are None because the monthly warning is not used.
    Notes:
        Supply new-cycle demand and matching product names when passing
        previous_results. Separate script runs do not retain these answers.
    """
    if product_inputs is None:
        product_inputs = products
    results = {}
    for name, inputs in product_inputs.items():
        policy = policies[inputs['policy']]
        if previous_results is None:
            opening_stock = inputs['A_initial']
            stock_received = inputs['received_initial']
        else:
            opening_stock, stock_received = carry_over(
                previous_results[name]['A'], previous_results[name]['quantity']
            )
        z = get_z_value(service_level)
        if inputs['policy'] == 'annual':
            history = inputs['annual_demand']
            average = average_annual_demand(history)
            sigma = annual_demand_std_dev(history)
            total_demand = history[-1]
            A = annual_stock_available(opening_stock, stock_received, total_demand)
            SS, S, quantity = annual_recommended_quantity(A, average, sigma, z)
            expected_remaining, colour, risk = None, None, None
        else:
            history = inputs['monthly_demand']
            average = average_monthly_demand(history)
            sigma = demand_std_dev(history)
            total_demand = sum(history)
            A = stock_available(opening_stock, stock_received, history)
            SS, S, quantity = recommended_quantity(
                A, average, sigma, z, policy['review_interval'], policy['lead_time']
            )
            expected_remaining, colour, risk = stockout_risk(
                A, average, policy['lead_time'], SS
            )
        results[name] = {
            'policy': inputs['policy'], 'unit': inputs['unit'], 'history': history,
            'total_demand': total_demand, 'average': average, 'sigma': sigma,
            'opening_stock': opening_stock, 'stock_received': stock_received,
            'A': A, 'SS': SS, 'S': S, 'quantity': quantity,
            'unit_price': inputs['unit_price'],
            'cost': order_cost(quantity, inputs['unit_price']),
            'expected_remaining': expected_remaining, 'colour': colour, 'risk': risk
        }
    return results


def print_summary(results):
    """Print results for each product, grouped by review policy.

    Args:
        results: Dictionary returned by calculate_results.
    Returns:
        None. Writes summaries to the terminal, including unit prices and
        purchasing costs. Only displayed quantities are rounded; the stored
        results are unchanged. Risk warnings print for monthly items only.
    """
    for key, policy in policies.items():
        print(f"\n{policy['title']} | {policy['period']}")
        print(f"T={policy['review_interval']} months; L={policy['lead_time']} months; "
              f"service level={service_level:.0%}; order={policy['order_month']}; "
              f"receipt={policy['receipt_month']}")
        for name, output in results.items():
            if output['policy'] != key:
                continue
            print(f"\n{name} ({output['unit']})")
            print(f"  Cycle demand: {output['total_demand']}")
            print(f"  Opening stock: {output['opening_stock']}; received: {output['stock_received']}")
            basis = 'annual' if key == 'annual' else 'monthly'
            print(f"  {basis.capitalize()} demand records: {output['history']}")
            print(f"  Average {basis} demand (rounded): {output['average']:.0f}")
            print(f"  On hand (A): {output['A']}")
            print(f"  Safety stock (SS): {math.ceil(output['SS'])}")
            print(f"  Target stock (S): {math.ceil(output['S'])}")
            print(f"  Recommended order: {output['quantity']}")
            print(f"  Unit price: R{output['unit_price']:.2f}")
            print(f"  Purchasing cost: R{output['cost']:,.2f}")
            if key == 'six_month':
                print(f"  Risk of stockout before delivery: {output['risk']} ({output['colour']})")


def write_html(results):
    """Fill the HTML template with the calculated product results.

    Args:
        results: Dictionary returned by calculate_results.
    Returns:
        None. Reads inventory_template.html beside this Python file and
        overwrites inventory_summary.html in the same folder. Monthly and
        annual products go into separate tables, each with unit price.
        Text is HTML-escaped. Numeric values are formatted for display only.
    Notes:
        Keep the template and Python file together. Change inputs in Python,
        rerun the script, then refresh the generated page in the browser.
    """
    monthly_rows = []
    annual_rows = []
    for name, output in results.items():
        # All displayed text is escaped; calculations remain unrounded.
        row = f"""<tr>
          <th scope="row">{escape(name)}</th>
          <td>{escape(output['unit'])}</td>
          <td>{output['A']}</td>
          <td>{output['average']:.0f}</td>
          <td>{math.ceil(output['SS'])}</td>
          <td>{math.ceil(output['S'])}</td>
          <td><strong>{output['quantity']}</strong></td>
          <td>R{output['unit_price']:,.2f}</td>
          <td>R{output['cost']:,.2f}</td>"""
        if output['policy'] == 'six_month':
            row += f'<td><span class="badge {output["colour"]}">{escape(output["risk"])}</span></td></tr>'
            monthly_rows.append(row)
        else:
            annual_rows.append(row + '</tr>')
    folder = Path(__file__).resolve().parent
    template = (folder / 'inventory_template.html').read_text(encoding='utf-8')
    page = template.replace('<!-- PRODUCT_ROWS -->', '\n'.join(monthly_rows))
    page = page.replace('<!-- ANNUAL_ROWS -->', '\n'.join(annual_rows))
    page = page.replace('<!-- SERVICE_LEVEL -->', f'{service_level:.0%}')
    for key, prefix in [('six_month', ''), ('annual', 'ANNUAL_')]:
        for field in ['review_interval', 'lead_time', 'order_month', 'receipt_month']:
            page = page.replace(f'<!-- {prefix}{field.upper()} -->', str(policies[key][field]))
    (folder / 'inventory_summary.html').write_text(page, encoding='utf-8')


if __name__ == '__main__':
    results = calculate_results()
    print_summary(results)
    write_html(results)

    # NEXT ANNUAL CYCLE: supply new annual histories, then use previous results.
    # next_book_inputs = {name: dict(data) for name, data in products.items()
    #                     if data['policy'] == 'annual'}
    # Update each annual_demand list by dropping its oldest year and appending
    # the new cycle's actual demand. Then call:
    # next_results = calculate_results(next_book_inputs, previous_results=results)
    # Initial values are ignored when previous_results is supplied.
