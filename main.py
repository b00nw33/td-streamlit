import streamlit as st
import csv
from datetime import datetime, timedelta
import calendar
import matplotlib.pyplot as plt
from collections import defaultdict
import io
import pandas as pd

# --- Core Logic Functions (adapted) ---

def load_transactions_from_text(text_data):
    """Load and aggregate transactions from pasted text."""
    transactions = defaultdict(float)
    if not text_data.strip():
        return {}

    lines = text_data.strip().splitlines()
    if not lines:
        return {}

    first_line_lower = lines[0].lower()
    has_header = 'date' in first_line_lower and 'amount' in first_line_lower

    if not has_header:
        try:
            datetime.strptime(lines[0].split(',')[0].strip(), "%Y-%m-%d")
            text_data_with_header = "date,amount\n" + text_data.strip()
        except (ValueError, IndexError):
            if not ('date' in lines[0].lower() and 'amount' in lines[0].lower()):
                st.error("Pasted data does not seem to have a 'date,amount' header, and the first line doesn't look like 'YYYY-MM-DD,value'. Please ensure the format is correct.")
                return defaultdict(float)
            text_data_with_header = text_data.strip()
    else:
        text_data_with_header = text_data.strip()

    try:
        file_like_object = io.StringIO(text_data_with_header)
        reader = csv.DictReader(file_like_object)
        for row_num, row in enumerate(reader, 1): # Add row_num for better error reporting
            try:
                date_str = row.get('date', '').strip() # Use .get for safety
                amount_str = row.get('amount', '').strip()

                if not date_str or not amount_str:
                    st.warning(f"Skipping row {row_num}: missing date or amount. Row content: {row}")
                    continue

                date = datetime.strptime(date_str, "%Y-%m-%d").date()
                amount = float(amount_str)
                transactions[date] += amount
            except KeyError: # Should be caught by .get now, but keep for safety
                st.error("CSV format error: Ensure columns are named 'date' and 'amount'.")
                return defaultdict(float)
            except ValueError as ve:
                st.error(f"Data conversion error in row {row_num} (content: {row}). Date should be YYYY-MM-DD, amount should be a number. Details: {ve}")
                return defaultdict(float)
    except Exception as e:
        st.error(f"⚠️ Error processing pasted transactions: {e}")
        return defaultdict(float)
    return dict(transactions)


def generate_daily_balances(start_balance, transactions, year, month):
    """Build daily balances by applying transactions day-by-day."""
    try:
        days_in_month = calendar.monthrange(year, month)[1]
    except calendar.IllegalMonthError: # Should not happen with current_date
        st.error(f"Invalid month: {month}. Please enter a month between 1 and 12.")
        return [], []
    except TypeError:
        st.error(f"Year and Month must be numbers.")
        return [], []

    first_day = datetime(year, month, 1).date()
    daily_balances = []
    dates = []
    current_balance = float(start_balance)

    for day_offset in range(days_in_month):
        current_day = first_day + timedelta(days=day_offset)
        current_balance += transactions.get(current_day, 0.0)
        daily_balances.append(current_balance)
        dates.append(current_day)
    return dates, daily_balances


def calculate_adb_and_suggestion(dates, daily_balances, target_adb, year, month):
    """
    Calculate ADB progress and recommend today's adjustment,
    considering all known future transactions.
    """
    if not dates or not daily_balances:
        return { # Return a default structure on error
            "sum_of_balances_up_to_yesterday": 0,
            "target_total_sum_for_month": 0,
            "projected_balance_today_pre_adj": 0,
            "ideal_balance_for_today": 0,
            "adjustment": 0,
            "required_avg_for_remaining_days": 0,
            "current_adb": 0,
            "days_in_month": calendar.monthrange(year,month)[1] if year and month else 30,
            "past_days_count": 0,
            "remaining_days_count_incl_today": 0,
            "today_date": datetime.today().date(),
            "month_has_passed": False,
            "is_today_in_month": False
        }

    today_date = datetime.today().date()
    yesterday_date = today_date - timedelta(days=1)
    
    first_day_of_month = datetime(year, month, 1).date()
    last_day_of_month = datetime(year, month, calendar.monthrange(year, month)[1]).date()

    # --- Determine time context ---
    past_days_count = 0 # Days strictly before today
    if today_date > first_day_of_month:
        past_days_count = (min(today_date, last_day_of_month + timedelta(days=1)) - first_day_of_month).days


    remaining_days_count_incl_today = 0
    if today_date <= last_day_of_month:
        remaining_days_count_incl_today = (last_day_of_month - today_date).days + 1
    
    month_has_passed = today_date > last_day_of_month
    is_today_in_month = first_day_of_month <= today_date <= last_day_of_month

    # --- Calculate sums based on projected daily_balances ---
    sum_of_balances_up_to_yesterday = sum(b for d, b in zip(dates, daily_balances) if d <= yesterday_date and d >= first_day_of_month)
    
    projected_balance_today_pre_adj = 0
    if is_today_in_month:
        projected_balance_today_pre_adj = next((b for d, b in zip(dates, daily_balances) if d == today_date), daily_balances[past_days_count] if past_days_count < len(daily_balances) else 0)

    sum_of_projected_balances_from_tomorrow = sum(b for d, b in zip(dates, daily_balances) if d > today_date and d <= last_day_of_month)

    # --- Core ADB calculations ---
    days_in_month = len(dates)
    current_adb = sum(daily_balances) / days_in_month if days_in_month > 0 else 0
    target_total_sum_for_month = float(target_adb) * days_in_month

    # --- Calculate ideal balance for today and adjustment ---
    ideal_balance_for_today = 0
    adjustment = 0
    
    if is_today_in_month :
        ideal_balance_for_today = target_total_sum_for_month - sum_of_balances_up_to_yesterday - sum_of_projected_balances_from_tomorrow
        adjustment = ideal_balance_for_today - projected_balance_today_pre_adj
    elif month_has_passed:
        # No adjustment possible, calculations are for review
        ideal_balance_for_today = projected_balance_today_pre_adj # Or N/A
        adjustment = 0


    # --- Calculate required average for remaining days (for informational purposes) ---
    required_avg_for_remaining_days = 0
    if remaining_days_count_incl_today > 0:
        balance_needed_from_today_onwards = target_total_sum_for_month - sum_of_balances_up_to_yesterday
        required_avg_for_remaining_days = balance_needed_from_today_onwards / remaining_days_count_incl_today
    elif is_today_in_month: # Last day of month
         required_avg_for_remaining_days = ideal_balance_for_today


    return {
        "sum_of_balances_up_to_yesterday": sum_of_balances_up_to_yesterday,
        "target_total_sum_for_month": target_total_sum_for_month,
        "projected_balance_today_pre_adj": projected_balance_today_pre_adj,
        "ideal_balance_for_today": ideal_balance_for_today,
        "adjustment": adjustment,
        "required_avg_for_remaining_days": required_avg_for_remaining_days,
        "current_adb": current_adb, # This is the ADB if month ended now with these balances
        "days_in_month": days_in_month,
        "past_days_count": past_days_count, # Days before today
        "remaining_days_count_incl_today": remaining_days_count_incl_today,
        "today_date": today_date,
        "month_has_passed": month_has_passed,
        "is_today_in_month": is_today_in_month
    }


def plot_balances_streamlit(dates, balances, required_avg, target_adb, year, month):
    if not dates or not balances:
        st.info("Not enough data to plot.")
        return None

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(dates, balances, label="Daily Balance (Projected)", marker="o", linestyle="-", markersize=5)
    ax.axhline(y=target_adb, color='green', linestyle='--', label=f"Target ADB (${target_adb:,.2f})")

    today_date = datetime.today().date()
    plot_required_avg_from = today_date

    if required_avg > 0 and plot_required_avg_from >= dates[0] and plot_required_avg_from <= dates[-1]:
        # Find index of plot_required_avg_from in dates
        try:
            start_idx = dates.index(plot_required_avg_from)
            ax.plot(dates[start_idx:], [required_avg] * len(dates[start_idx:]), color='red', linestyle='--', label=f"Required Avg from Today (${required_avg:,.2f})")
        except ValueError:
            future_dates_for_plot = [d for d in dates if d >= plot_required_avg_from]
            if future_dates_for_plot:
                 ax.plot(future_dates_for_plot, [required_avg] * len(future_dates_for_plot), color='red', linestyle='--', label=f"Required Avg from {future_dates_for_plot[0].strftime('%b %d')} (${required_avg:,.2f})")

    ax.axvline(x=today_date, color='gray', linestyle=':', label="Today")
    ax.set_title(f"Daily Balances for {calendar.month_name[month]} {year} and ADB Target")
    ax.set_xlabel("Date")
    ax.set_ylabel("Balance ($)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    plt.xticks(rotation=45)
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend()
    plt.tight_layout()
    return fig

# --- Streamlit App UI ---
st.set_page_config(layout="wide")
st.title("📈 Average Daily Balance (ADB) Calculator & Forecaster")
st.markdown(f"**Analyzing for: {calendar.month_name[datetime.today().month]} {datetime.today().year}**")


# Sidebar for inputs
st.sidebar.header("Configuration")
current_app_date = datetime.today() # Date context for the app run
app_year = current_app_date.year
app_month = current_app_date.month

start_balance = st.sidebar.number_input("Starting Balance (end of previous month)", value=100000.00, format="%.2f", step=1000.0)
target_adb = st.sidebar.number_input("Target ADB for the Month", value=100000.00, format="%.2f", step=1000.0)

st.sidebar.subheader("Transactions")
default_transactions = """date,amount
# Example: YYYY-MM-DD,amount
# 2024-07-15,500.20
# 2024-07-16,-120.00
"""
pasted_transactions = st.sidebar.text_area(
    "Paste Transactions (CSV format: date,amount)",
    value=default_transactions,
    height=200,
    help="Each line: YYYY-MM-DD,amount (negative for withdrawal). Include a header 'date,amount' or paste data directly."
)

calculate_button = st.sidebar.button("📊 Calculate ADB & Suggestion")

if calculate_button:
    if target_adb <= 0:
        st.error("Target ADB must be a positive value.")
    else:
        transactions_dict = load_transactions_from_text(pasted_transactions)
        if isinstance(transactions_dict, defaultdict) and not dict(transactions_dict):
             st.warning("Proceeding with calculation assuming no transactions due to previous error, or no transactions were input.")
             transactions_dict = {}

        dates, daily_balances = generate_daily_balances(start_balance, transactions_dict, app_year, app_month)

        if not dates:
            st.error("Could not generate daily balances. This is unexpected for the current month.")
        else:
            results = calculate_adb_and_suggestion(dates, daily_balances, target_adb, app_year, app_month)

            st.header(f"ADB Analysis for {calendar.month_name[app_month]} {app_year}")

            col1, col2, col3 = st.columns(3)
            col1.metric("Target ADB", f"${target_adb:,.2f}")
            col2.metric("Projected Month-End ADB", f"${results['current_adb']:,.2f}")

            if results['month_has_passed']:
                if results['current_adb'] >= target_adb:
                    col3.success(f"Met Target! Final ADB: ${results['current_adb']:,.2f}")
                else:
                    col3.error(f"Missed Target. Final ADB: ${results['current_adb']:,.2f}")
            elif results['is_today_in_month']:
                if results['adjustment'] <= 0: # No deposit needed or withdrawal suggested
                     col3.success("On Track for Today!")
                else: # Deposit suggested
                     col3.warning("Needs Deposit Today")
            else: # Month hasn't started yet
                col3.info("Month has not started yet.")


            st.subheader("📊 Key Figures for Today " + f"({results['today_date'].strftime('%Y-%m-%d')})")
            details_col1, details_col2 = st.columns(2)
            with details_col1:
                st.write(f"**Sum of balances up to yesterday ({ (results['today_date'] - timedelta(days=1)).strftime('%Y-%m-%d')}):** ${results['sum_of_balances_up_to_yesterday']:,.2f}")
                st.write(f"**Total balance-days needed for target ADB:** ${results['target_total_sum_for_month']:,.2f}")
                st.write(f"**Days in month:** {results['days_in_month']}")
                st.write(f"**Past days (before today):** {results['past_days_count']}")
                st.write(f"**Remaining days (incl. today):** {results['remaining_days_count_incl_today']}")
                
            with details_col2:
                st.write(f"**Projected balance today (before adjustment):** ${results['projected_balance_today_pre_adj']:,.2f}")
                if results['is_today_in_month']:
                    st.write(f"**Target balance for today (to hit ADB):** ${results['ideal_balance_for_today']:,.2f}")
                st.write(f"**Required average for remaining days (incl. today):** ${results['required_avg_for_remaining_days']:,.2f}")


            if results['is_today_in_month'] and not results['month_has_passed']:
                st.markdown("---")
                st.subheader("💡 Today's Action")
                if results['adjustment'] > 0:
                    st.markdown(f"<h3 style='color: orange;'>💰 Suggest DEPOSIT of: ${results['adjustment']:,.2f}</h3>", unsafe_allow_html=True)
                    st.markdown("_This deposit would bring today's balance to the ideal level, considering all other known past and future transactions, to achieve the target ADB._")
                elif results['adjustment'] < 0:
                    st.markdown(f"<h3 style='color: lightgreen;'>💸 Suggest WITHDRAWAL of: ${abs(results['adjustment']):,.2f}</h3>", unsafe_allow_html=True)
                    st.markdown("_This withdrawal is possible while today's balance remains at/above the ideal level, considering all other known past and future transactions, to achieve the target ADB._")
                else:
                    st.markdown("<h3 style='color: green;'>✅ No adjustment needed today — on track!</h3>", unsafe_allow_html=True)
                    st.markdown("_Today's projected balance aligns with what's needed to hit the target ADB, considering all other transactions._")
            elif results['month_has_passed']:
                st.info("The month has ended. Suggestions are not applicable.")
            else: # Month not yet started
                st.info("The month has not started yet. Check back on the first day of the month for suggestions.")


            st.subheader("📈 Balance Trend")
            fig = plot_balances_streamlit(dates, daily_balances, results['required_avg_for_remaining_days'], target_adb, app_year, app_month)
            if fig:
                st.pyplot(fig)
            else:
                st.write("Could not generate plot for balances.")

            if st.checkbox("Show Daily Balances Table", key="show_table_checkbox"):
                if dates and daily_balances:
                    df_balances = pd.DataFrame({'Date': dates, 'Balance': daily_balances})
                    df_balances['Date'] = pd.to_datetime(df_balances['Date']).dt.strftime('%Y-%m-%d (%a)')
                    df_balances['Balance'] = df_balances['Balance'].map('${:,.2f}'.format)
                    st.dataframe(df_balances, use_container_width=True)
                else:
                    st.write("No daily balance data to display in table.")
else:
    st.info("ℹ️ Configure parameters in the sidebar and click 'Calculate ADB & Suggestion'.")
    st.markdown("""
    ### How to use:
    1.  **Starting Balance**: Enter your account balance as of the end of the day *before* the first day of the current month.
    2.  **Target ADB**: Enter the Average Daily Balance you aim to achieve for the current month.
    3.  **Paste Transactions**:
        *   Paste your transactions (for any date, past or future) in CSV format.
        *   Each line: `YYYY-MM-DD,amount` (negative for withdrawal).
        *   Example: `2024-07-15,500.20` or `2024-07-16,-120.00`.
        *   You can include a header row `date,amount` or paste data directly.
    4.  Click **Calculate ADB & Suggestion**.

    The app will analyze for the **current month** and provide a suggestion for today's balance adjustment.
    """)
