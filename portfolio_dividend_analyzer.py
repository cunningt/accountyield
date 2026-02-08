#!/usr/bin/env python3
"""
Portfolio Dividend Growth Analyzer

Reads portfolio export CSV, fetches dividend metrics using yfinance,
and displays holdings sorted by dividend growth with yield and quantity.
"""

import csv
import sys
import yfinance as yf
import time
from typing import Optional


def parse_portfolio_csv(csv_file: str) -> list:
    """
    Parse the exported portfolio CSV and extract symbol, quantity, and cost basis.

    Args:
        csv_file: Path to the portfolio export CSV file

    Returns:
        List of dictionaries with symbol, quantity, and cost_basis
    """
    holdings = []

    with open(csv_file, 'r') as f:
        lines = f.readlines()

    # Find the header line (contains "Symbol")
    header_idx = None
    for i, line in enumerate(lines):
        if 'Symbol' in line and 'Quantity' in line:
            header_idx = i
            break

    if header_idx is None:
        print("Error: Could not find header row in CSV")
        return holdings

    # Parse data rows (skip header, stop at "Balances")
    for i in range(header_idx + 1, len(lines)):
        line = lines[i].strip()

        # Stop at balances section or empty lines
        if not line or 'Balances' in line or 'Money accounts' in line:
            break

        # Parse CSV row
        row = list(csv.reader([line]))[0]

        if len(row) < 7:
            continue

        symbol = row[0].strip().strip('"').replace('!', '').strip()
        quantity_str = row[2].strip().strip('"').replace(',', '')
        cost_basis_str = row[6].strip().strip('"').replace('$', '').replace(',', '')

        # Skip if no valid symbol or quantity
        if not symbol or symbol == '--' or not quantity_str:
            continue

        try:
            quantity = float(quantity_str)
            cost_basis = float(cost_basis_str) if cost_basis_str and cost_basis_str != '--' else 0.0

            holdings.append({
                'symbol': symbol,
                'quantity': quantity,
                'cost_basis': cost_basis
            })
        except ValueError:
            continue

    return holdings


def calculate_cagr(start_value: float, end_value: float, years: float) -> float:
    """Calculate Compound Annual Growth Rate."""
    if start_value <= 0 or end_value <= 0 or years <= 0:
        return 0.0
    return ((end_value / start_value) ** (1 / years) - 1) * 100


def get_dividend_metrics(symbol: str) -> dict:
    """
    Fetch dividend metrics for a stock using yfinance.

    Args:
        symbol: Stock ticker symbol

    Returns:
        Dictionary with current_price, dividend_yield, div_growth_1yr, div_growth_5yr
    """
    result = {
        'current_price': None,
        'dividend_yield': None,
        'annual_dividend': None,
        'div_growth_1yr': None,
        'div_growth_5yr': None
    }

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info

        # Get current price
        result['current_price'] = info.get('currentPrice') or info.get('regularMarketPrice')

        # Get dividend yield (Yahoo Finance returns as decimal, e.g., 0.0132 for 1.32%)
        result['dividend_yield'] = info.get('dividendYield')
        if result['dividend_yield']:
            # Check if already in percentage form (>1) or decimal form (<1)
            if result['dividend_yield'] < 1:
                result['dividend_yield'] = result['dividend_yield'] * 100  # Convert decimal to percentage
            # else: already in percentage form, use as-is

        # Get annual dividend amount (dividendRate is annualized dividend per share)
        result['annual_dividend'] = info.get('dividendRate')

        # If dividendRate not available, calculate from current price and yield
        if result['annual_dividend'] is None and result['current_price'] and result['dividend_yield']:
            result['annual_dividend'] = result['current_price'] * (result['dividend_yield'] / 100)

        # Get dividend history for growth calculations
        dividends = ticker.dividends

        if len(dividends) > 0:
            # Calculate 1-year dividend growth
            try:
                one_year_ago = dividends.index[-1] - pd.Timedelta(days=365)
                recent_div = dividends.iloc[-1]

                # Get dividend from ~1 year ago
                one_year_divs = dividends[dividends.index <= one_year_ago]
                if len(one_year_divs) > 0:
                    old_div = one_year_divs.iloc[-1]
                    if old_div > 0:
                        result['div_growth_1yr'] = ((recent_div - old_div) / old_div) * 100
            except:
                pass

            # Calculate 5-year dividend growth (CAGR)
            try:
                five_years_ago = dividends.index[-1] - pd.Timedelta(days=5*365)
                recent_div = dividends.iloc[-1]

                # Get dividend from ~5 years ago
                five_year_divs = dividends[dividends.index <= five_years_ago]
                if len(five_year_divs) > 0:
                    old_div = five_year_divs.iloc[-1]
                    result['div_growth_5yr'] = calculate_cagr(old_div, recent_div, 5.0)
            except:
                pass

    except Exception as e:
        print(f"  Error fetching data for {symbol}: {str(e)}")

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python portfolio_dividend_analyzer.py <export_csv_file>")
        print("\nExample: python portfolio_dividend_analyzer.py ExportData02012026100730.csv")
        sys.exit(1)

    csv_file = sys.argv[1]

    print("=" * 80)
    print("PORTFOLIO DIVIDEND GROWTH ANALYZER")
    print("=" * 80)
    print()

    # Parse portfolio CSV
    print(f"Reading portfolio from: {csv_file}")
    holdings = parse_portfolio_csv(csv_file)
    print(f"Found {len(holdings)} holdings\n")

    # Fetch dividend metrics for each holding
    print("Fetching dividend data from Yahoo Finance...")
    print("(This may take a few minutes with rate limiting)\n")

    portfolio_data = []
    total_weighted_growth_1yr = 0.0
    total_weighted_growth_5yr = 0.0
    total_value = 0.0
    total_annual_dividend = 0.0

    for i, holding in enumerate(holdings, 1):
        symbol = holding['symbol']
        quantity = holding['quantity']

        print(f"[{i}/{len(holdings)}] Fetching {symbol}...")

        metrics = get_dividend_metrics(symbol)

        # Calculate position value
        current_price = metrics['current_price']
        position_value = (current_price * quantity) if current_price else 0.0

        # Calculate annual dividend income from this position
        annual_dividend_income = 0.0
        if metrics['annual_dividend'] and quantity:
            annual_dividend_income = metrics['annual_dividend'] * quantity

        # Add to portfolio data
        portfolio_data.append({
            'symbol': symbol,
            'quantity': quantity,
            'current_price': current_price,
            'position_value': position_value,
            'dividend_yield': metrics['dividend_yield'],
            'annual_dividend': metrics['annual_dividend'],
            'annual_dividend_income': annual_dividend_income,
            'div_growth_1yr': metrics['div_growth_1yr'],
            'div_growth_5yr': metrics['div_growth_5yr']
        })

        # Add to total annual dividend
        total_annual_dividend += annual_dividend_income

        # Calculate weighted dividend growth for account
        if position_value > 0:
            # For 1-year weighted growth
            if metrics['div_growth_1yr'] is not None:
                total_weighted_growth_1yr += metrics['div_growth_1yr'] * position_value

            # For 5-year weighted growth (use 1yr as fallback if 5yr not available)
            growth_rate = metrics['div_growth_5yr'] if metrics['div_growth_5yr'] is not None else metrics['div_growth_1yr']
            if growth_rate is not None:
                total_weighted_growth_5yr += growth_rate * position_value

            total_value += position_value

        # Rate limiting - be nice to Yahoo Finance
        if i < len(holdings):
            time.sleep(5)

    # Calculate overall portfolio dividend growth
    overall_div_growth_1yr = (total_weighted_growth_1yr / total_value) if total_value > 0 else 0.0
    overall_div_growth_5yr = (total_weighted_growth_5yr / total_value) if total_value > 0 else 0.0

    # Filter out stocks that don't pay dividends
    dividend_paying_stocks = [h for h in portfolio_data if h['dividend_yield'] is not None and h['dividend_yield'] > 0]

    # Sort by dividend growth (1-year)
    dividend_paying_stocks.sort(key=lambda x: x['div_growth_1yr'] if x['div_growth_1yr'] is not None else -999, reverse=True)

    # Calculate portfolio dividend yield
    portfolio_dividend_yield = (total_annual_dividend / total_value * 100) if total_value > 0 else 0.0

    # Display results
    print("\n" + "=" * 80)
    print("PORTFOLIO DIVIDEND GROWTH ANALYSIS")
    print("=" * 80)
    print()
    print(f"💰 TOTAL ANNUAL DIVIDEND INCOME (2026): ${total_annual_dividend:,.2f}")
    print(f"   Portfolio Dividend Yield: {portfolio_dividend_yield:.2f}%")
    print()
    print(f"📈 Portfolio Dividend Growth (1-Year, weighted): {overall_div_growth_1yr:.2f}%")
    print(f"📈 Portfolio Dividend Growth (5-Year, weighted): {overall_div_growth_5yr:.2f}%")
    print()
    print(f"Total Portfolio Value: ${total_value:,.2f}")
    print(f"Dividend-Paying Holdings: {len(dividend_paying_stocks)}/{len(holdings)}")
    print()
    print("-" * 100)
    print(f"{'Symbol':<8} {'Yield %':<10} {'Ann Div $':<12} {'1Yr Grw %':<12} {'5Yr Grw %':<12} {'Quantity':<10} {'Ann Income':<15}")
    print("-" * 100)

    for holding in dividend_paying_stocks:
        symbol = holding['symbol']
        div_yield = f"{holding['dividend_yield']:.2f}" if holding['dividend_yield'] is not None else "N/A"
        ann_div = f"${holding['annual_dividend']:.2f}" if holding['annual_dividend'] is not None else "N/A"
        div_1yr = f"{holding['div_growth_1yr']:.2f}" if holding['div_growth_1yr'] is not None else "N/A"
        div_5yr = f"{holding['div_growth_5yr']:.2f}" if holding['div_growth_5yr'] is not None else "N/A"
        quantity = f"{holding['quantity']:.1f}"
        ann_income = f"${holding['annual_dividend_income']:,.2f}" if holding['annual_dividend_income'] > 0 else "N/A"

        print(f"{symbol:<8} {div_yield:<10} {ann_div:<12} {div_1yr:<12} {div_5yr:<12} {quantity:<10} {ann_income:<15}")

    print("-" * 100)
    print()

    # Summary statistics
    stocks_with_div_growth = sum(1 for h in dividend_paying_stocks if h['div_growth_1yr'] is not None)

    print(f"Dividend-paying stocks with growth data: {stocks_with_div_growth}/{len(dividend_paying_stocks)}")
    print()

    # Show top dividend income contributors
    print("=" * 80)
    print("TOP 10 DIVIDEND INCOME CONTRIBUTORS")
    print("=" * 80)
    print()

    # Sort by annual dividend income
    top_income_stocks = sorted(
        [h for h in dividend_paying_stocks if h['annual_dividend_income'] > 0],
        key=lambda x: x['annual_dividend_income'],
        reverse=True
    )[:10]

    print(f"{'Symbol':<8} {'Quantity':<12} {'Ann Div/Share':<15} {'Annual Income':<18} {'% of Total'}")
    print("-" * 80)

    for holding in top_income_stocks:
        symbol = holding['symbol']
        quantity = f"{holding['quantity']:.1f}"
        ann_div = f"${holding['annual_dividend']:.2f}" if holding['annual_dividend'] else "N/A"
        ann_income = f"${holding['annual_dividend_income']:,.2f}"
        pct_of_total = (holding['annual_dividend_income'] / total_annual_dividend * 100) if total_annual_dividend > 0 else 0
        pct_str = f"{pct_of_total:.1f}%"

        print(f"{symbol:<8} {quantity:<12} {ann_div:<15} {ann_income:<18} {pct_str}")

    print("-" * 80)
    print()

    # Forecast future dividend income based on 5-year weighted growth
    print("=" * 80)
    print("DIVIDEND INCOME FORECAST (based on 5-year weighted growth)")
    print("=" * 80)
    print()
    print(f"Dividend Growth Rate: {overall_div_growth_5yr:.2f}% (weighted average, 5yr with 1yr fallback)")
    print(f"Portfolio Increase: 3.00% (additional capital deployed annually)")
    print(f"Combined Growth Rate: {overall_div_growth_5yr + 3.00:.2f}%")
    print()

    # Calculate forecasts with both dividend growth and portfolio increase
    portfolio_increase_rate = 3.00
    combined_growth_rate = overall_div_growth_5yr + portfolio_increase_rate

    forecast_2027 = total_annual_dividend * (1 + combined_growth_rate / 100)
    forecast_2028 = forecast_2027 * (1 + combined_growth_rate / 100)
    forecast_2029 = forecast_2028 * (1 + combined_growth_rate / 100)
    forecast_2030 = forecast_2029 * (1 + combined_growth_rate / 100)

    # Calculate cumulative growth
    total_growth_2027 = ((forecast_2027 - total_annual_dividend) / total_annual_dividend * 100) if total_annual_dividend > 0 else 0
    total_growth_2028 = ((forecast_2028 - total_annual_dividend) / total_annual_dividend * 100) if total_annual_dividend > 0 else 0
    total_growth_2029 = ((forecast_2029 - total_annual_dividend) / total_annual_dividend * 100) if total_annual_dividend > 0 else 0
    total_growth_2030 = ((forecast_2030 - total_annual_dividend) / total_annual_dividend * 100) if total_annual_dividend > 0 else 0

    print(f"{'Year':<8} {'Annual Dividend':<20} {'vs 2026':<20} {'Monthly Income':<20}")
    print("-" * 80)
    print(f"{'2026':<8} ${total_annual_dividend:>12,.2f}       {'':<20} ${total_annual_dividend/12:>12,.2f}")
    print(f"{'2027':<8} ${forecast_2027:>12,.2f}       +{total_growth_2027:>6.2f}%           ${forecast_2027/12:>12,.2f}")
    print(f"{'2028':<8} ${forecast_2028:>12,.2f}       +{total_growth_2028:>6.2f}%           ${forecast_2028/12:>12,.2f}")
    print(f"{'2029':<8} ${forecast_2029:>12,.2f}       +{total_growth_2029:>6.2f}%           ${forecast_2029/12:>12,.2f}")
    print(f"{'2030':<8} ${forecast_2030:>12,.2f}       +{total_growth_2030:>6.2f}%           ${forecast_2030/12:>12,.2f}")
    print("-" * 80)
    print()

    # Show total increase
    total_increase = forecast_2030 - total_annual_dividend
    print(f"Total Dividend Increase (2026-2030): ${total_increase:,.2f}")
    print(f"Dividend CAGR: {overall_div_growth_5yr:.2f}%")
    print(f"Portfolio Growth (capital additions): {portfolio_increase_rate:.2f}%")
    print(f"Combined CAGR: {combined_growth_rate:.2f}%")
    print()

    # Assumptions and notes
    print("Assumptions:")
    print("• Constant dividend growth rate (weighted 5-year average)")
    print("• 3% annual portfolio increase (new capital deployed at same yield)")
    print("• No dividend cuts or suspensions")
    print("• New capital earns portfolio average yield and growth rate")
    print("• Past performance does not guarantee future results")
    print()


if __name__ == "__main__":
    import pandas as pd  # Import here to avoid issues if not needed
    main()
