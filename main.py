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
        for row_num, row in enumerate(reader, 1):
            try:
                date_str = row.get('date', '').strip()
                amount_str = row.get('amount', '').strip()

                if not date_str or not amount_str:
                    st.warning(f"Skipping row {row_num}: missing date or amount. Row content: {row}")
                    continue

                date = datetime.strptime(date_str, "%Y-%m-%d").date()
                amount = float(amount_str)
                transactions[date] += amount
            except KeyError:
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
    except calendar.IllegalMonthError:
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


def calculate_adb_and_suggestion_original(dates, daily_balances, target_adb, year, month):
    """
    Original ADB suggestion logic:
    Calculate ADB progress and recommend today's adjustment based on what's needed
    for remaining days assuming an even average balance.
    Does NOT try to precisely adjust today's balance by accounting for all specific future transactions.
    """
    if not dates or not daily_balances:
        return { # Default structure
            "sum_of_balances_so_far": 0,
            "total_required_balance_for_month": 0,
            "remaining_balance_needed": 0,
            "required_avg_from_today": 0,
            "todays_balance": 0,
            "adjustment": 0,
            "future_days": 0,
            "past_days_count":0,
            "current_adb": 0,
            "days_in_month": calendar.monthrange(year,month)[1] if year and month else 30,
            "today_date": datetime.today().date(),
            "month_has_passed": False,
            "is_today_in_month": False
        }

    today_date = datetime.today().date()
    yesterday_date = today_date - timedelta(days=1)

    first_day_of_month = datetime(year, month, 1).date()
    last_day_of_month = datetime(year, month, calendar.monthrange(year, month)[1]).date()

    days_in_month = len(dates)

    # Determine past days (up to yesterday, relevant to the selected month)
    past_days_count = 0
    if today_date > first_day_of_month: # If today is after the start of the month
        # Count days from start_of_month up to 'yesterday', capped by end_of_month
        past_days_count = (min(yesterday_date, last_day_of_month) - first_day_of_month).days + 1
        past_days_count = max(0, past_days_count) # Ensure non-negative
    elif today_date <= first_day_of_month: # If today is before or on the first day
        past_days_count = 0


    # Determine future days (from today onwards, relevant to the selected month)
    future_days_count = 0
    if today_date <= last_day_of_month: # If today is within the month
        future_days_count = (last_day_of_month - today_date).days + 1
    else: # Today is after the month has ended
        future_days_count = 0

    # Sum of balances for past days
    sum_of_balances_so_far = sum(
        balance for date, balance in zip(dates, daily_balances)
        if date >= first_day_of_month and date <= yesterday_date and date <= last_day_of_month
    )

    total_required_balance_for_month = float(target_adb) * days_in_month
    remaining_balance_needed = total_required_balance_for_month - sum_of_balances_so_far
    
    required_avg_from_today = 0
    if future_days_count > 0:
        required_avg_from_today = remaining_balance_needed / future_days_count
    
    # Get today's balance (or first future day's balance if today is past)
    todays_projected_balance = 0
    if today_date <= last_day_of_month and today_date >= first_day_of_month :
        try:
            today_idx = dates.index(today_date)
            todays_projected_balance = daily_balances[today_idx]
        except ValueError: # Today not in dates (e.g. weekend, or app run after month end)
             # If today is not in the list (e.g., past month end), try to get the last known balance
             if daily_balances: todays_projected_balance = daily_balances[-1]
    elif today_date > last_day_of_month and daily_balances:
        todays_projected_balance = daily_balances[-1] # Month ended, show last balance
    elif not daily_balances:
        todays_projected_balance = 0


    adjustment = 0
    if future_days_count > 0 : # Only suggest adjustment if there are future days in this month
        adjustment = required_avg_from_today - todays_projected_balance

    current_adb = sum(daily_balances) / days_in_month if days_in_month > 0 else 0
    month_has_passed = today_date > last_day_of_month
    is_today_in_month = first_day_of_month <= today_date <= last_day_of_month


    return {
        "sum_of_balances_so_far": sum_of_balances_so_far,
        "total_required_balance_for_month": total_required_balance_for_month,
        "remaining_balance_needed": remaining_balance_needed,
        "required_avg_from_today": required_avg_from_today,
        "todays_balance": todays_projected_balance, # This is balance on today_date
        "adjustment": adjustment,
        "future_days": future_days_count,
        "past_days_count": past_days_count,
        "current_adb": current_adb,
        "days_in_month": days_in_month,
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

    # Only plot required_avg line if today is within the month and there are future days for it
    if required_avg > 0 and plot_required_avg_from >= dates[0] and plot_required_avg_from <= dates[-1]:
        try:
            start_idx = dates.index(plot_required_avg_from)
            # Ensure the line is plotted only for the segment from today onwards
            ax.plot(dates[start_idx:], [required_avg] * len(dates[start_idx:]), color='red', linestyle='--', label=f"Required Avg from Today (${required_avg:,.2f})")
        except ValueError: # If today is not exactly in dates (e.g. weekend for some reason)
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
current_app_date = datetime.today()
app_year = current_app_date.year
app_month = current_app_date.month
st.markdown(f"**Analyzing for: {calendar.month_name[app_month]} {app_year}**")


# Sidebar for inputs
st.sidebar.header("Configuration")

start_balance = st.sidebar.number_input("Starting Balance (end of previous month)", value=100000.00, format="%.2f", step=1000.0)
target_adb = st.sidebar.number_input("Target ADB for the Month", value=100000.00, format="%.2f", step=1000.0)

st.sidebar.subheader("Transactions")
default_transactions_text = """date,amount
2025-05-1,642.7
2025-05-1,2.56
2025-05-7,2955.5
2025-05-13,205.47
2025-05-17,-3162.87
"""
# Note: The default transactions use 2025. If running in a different year,
# the app will still analyze for the *current* year/month.
# For the default to be immediately relevant, you might want to update it
# or inform the user if the default dates are outside the current analysis period.
# For simplicity here, we'll use the provided default.

pasted_transactions = st.sidebar.text_area(
    "Paste Transactions (CSV format: date,amount)",
    value=default_transactions_text,
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
            results = calculate_adb_and_suggestion_original(dates, daily_balances, target_adb, app_year, app_month)

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
                 # Check if today's balance meets the required average for remaining days
                if results['todays_balance'] >= results['required_avg_from_today'] and results['required_avg_from_today'] > 0 :
                     col3.success("On Track for Today!")
                elif results['required_avg_from_today'] > 0 : # Implies today's balance is below
                     col3.warning("Needs Adjustment Today")
                else: # required_avg might be 0 if no future days or target already met/exceeded a lot
                    if results['current_adb'] >= target_adb:
                         col3.success("Likely Exceeding Target")
                    else:
                         col3.info("Review Details")
            else: # Month hasn't started yet or other edge case
                col3.info("Month not started or check dates.")


            st.subheader("📊 Key Figures")
            details_col1, details_col2 = st.columns(2)
            with details_col1:
                st.write(f"**Sum of balances up to yesterday ({ (results['today_date'] - timedelta(days=1)).strftime('%Y-%m-%d')}):** ${results['sum_of_balances_so_far']:,.2f}")
                st.write(f"**Total balance-days needed for target ADB:** ${results['total_required_balance_for_month']:,.2f}")
                st.write(f"**Remaining balance-days needed:** ${results['remaining_balance_needed']:,.2f}")

            with details_col2:
                st.write(f"**Days in month:** {results['days_in_month']}")
                st.write(f"**Past days (before today):** {results['past_days_count']}")
                st.write(f"**Remaining days (incl. today):** {results['future_days']}")
                st.write(f"**Required average balance from today ({results['today_date'].strftime('%Y-%m-%d')}):** ${results['required_avg_from_today']:,.2f}")
                st.write(f"**Today's projected balance (before adjustment):** ${results['todays_balance']:,.2f}")


            if results['is_today_in_month'] and not results['month_has_passed'] and results['future_days'] > 0:
                st.markdown("---")
                st.subheader("💡 Today's Action Suggestion")
                if results['adjustment'] > 0:
                    st.markdown(f"<h3 style='color: orange;'>💰 Suggest DEPOSIT of: ${results['adjustment']:,.2f}</h3>", unsafe_allow_html=True)
                    st.markdown("_This deposit would bring today's balance to the required average for the remaining days._")
                elif results['adjustment'] < 0:
                    st.markdown(f"<h3 style='color: lightgreen;'>💸 Suggest WITHDRAWAL of: ${abs(results['adjustment']):,.2f}</h3>", unsafe_allow_html=True)
                    st.markdown("_This withdrawal is possible while maintaining today's balance at/above the required average for the remaining days._")
                else:
                    st.markdown("<h3 style='color: green;'>✅ No adjustment needed today — on track!</h3>", unsafe_allow_html=True)
                    st.markdown("_Today's projected balance aligns with the required average for the remaining days._")
            elif results['month_has_passed']:
                st.info("The month has ended. Suggestions are not applicable.")
            elif not results['is_today_in_month']:
                st.info("Today is outside the current analysis month or month has not started. No suggestion applicable for today.")
            elif results['future_days'] == 0 and results['is_today_in_month']: # Last day of month
                st.info("Today is the last day of the month. The projected balance for today will determine the final ADB outcome. No 'average for remaining days' applies.")


            st.subheader("📈 Balance Trend")
            fig = plot_balances_streamlit(dates, daily_balances, results['required_avg_from_today'], target_adb, app_year, app_month)
            if fig:
                st.pyplot(fig)
            else:
                st.write("Could not generate plot for balances.")

            st.subheader("📋 Daily Balances Table")
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
        *   The app will use these to project daily balances for the **current month**.
    4.  Click **Calculate ADB & Suggestion**.

    The app will analyze for the **current month** and provide a suggestion for today's balance adjustment based on an even distribution of the remaining required balance-days.
    """)
