import streamlit as st
import csv
from datetime import datetime, timedelta
import calendar
import matplotlib.pyplot as plt
from collections import defaultdict
import io # Required for StringIO to handle text as a file

# --- Core Logic Functions (slightly adapted for Streamlit) ---

def load_transactions_from_text(text_data):
    """Load and aggregate transactions from pasted text."""
    transactions = defaultdict(float)
    if not text_data.strip():
        # st.info("No transactions pasted. Proceeding without transactions.")
        return {}

    # Add a header if it's not present, assuming 'date,amount' format
    lines = text_data.strip().splitlines()
    if not lines:
        return {}
    
    # Heuristic to check for header. If first line doesn't look like a date, assume no header
    # or if it explicitly contains 'date' and 'amount' (case-insensitive)
    first_line_lower = lines[0].lower()
    has_header = 'date' in first_line_lower and 'amount' in first_line_lower
    
    if not has_header:
        # Simple check: if first token doesn't parse as date, it might be a header.
        # For simplicity, we'll assume if not explicitly 'date,amount', user might provide headerless.
        # A more robust check would be to try parsing the first line as data.
        # For this app, let's assume user will provide 'date,amount' or just the data.
        # If they provide just data, we prepend a header.
        # A common mistake is to paste data without a header.
        try:
            # Try to parse first field of first line as date
            datetime.strptime(lines[0].split(',')[0].strip(), "%Y-%m-%d")
            # If successful, it's data, so prepend header
            text_data_with_header = "date,amount\n" + text_data.strip()
        except (ValueError, IndexError):
            # If parsing fails, it might be a header already, or malformed.
            # If it contains 'date' and 'amount' it's a header. Otherwise, it's malformed.
            if not ('date' in lines[0].lower() and 'amount' in lines[0].lower()):
                st.error("Pasted data does not seem to have a 'date,amount' header, and the first line doesn't look like 'YYYY-MM-DD,value'. Please ensure the format is correct.")
                return {} # Return empty if format is clearly wrong
            text_data_with_header = text_data.strip() # Assume it has a header
    else:
        text_data_with_header = text_data.strip()


    try:
        # Use io.StringIO to treat the string as a file
        file_like_object = io.StringIO(text_data_with_header)
        reader = csv.DictReader(file_like_object)
        for row in reader:
            try:
                date_str = row['date'].strip()
                amount_str = row['amount'].strip()
                
                if not date_str or not amount_str: # Skip empty lines or rows with missing data
                    continue

                date = datetime.strptime(date_str, "%Y-%m-%d").date()
                amount = float(amount_str)
                transactions[date] += amount
            except KeyError:
                st.error("CSV format error: Ensure columns are named 'date' and 'amount'.")
                return defaultdict(float) # return empty on error
            except ValueError as ve:
                st.error(f"Data conversion error in row: {row}. Date should be YYYY-MM-DD, amount should be a number. Details: {ve}")
                return defaultdict(float) # return empty on error

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
    except TypeError: # If year or month is not an int
        st.error(f"Year and Month must be numbers.")
        return [], []
        
    first_day = datetime(year, month, 1).date()

    daily_balances = []
    dates = []
    current_balance = float(start_balance) # Ensure it's float

    for day_offset in range(days_in_month):
        current_day = first_day + timedelta(days=day_offset)
        current_balance += transactions.get(current_day, 0.0)
        daily_balances.append(current_balance)
        dates.append(current_day)

    return dates, daily_balances


def calculate_adb_and_suggestion(dates, daily_balances, target_adb, selected_year, selected_month):
    """Calculate ADB progress and recommend today's adjustment."""
    if not dates or not daily_balances: # Handle empty inputs if date generation failed
        return {
            "sum_of_balances_so_far": 0,
            "total_required_balance_for_month": 0,
            "remaining_balance_needed": 0,
            "required_avg": 0,
            "todays_balance": 0,
            "adjustment": 0,
            "future_days": 0,
            "current_adb": 0,
            "on_track": False
        }

    today = datetime.today().date()
    # If the selected month/year is in the past or far future, 'today' might not be relevant
    # We should consider 'today' relative to the selected month.
    # If selected month is past, all days are "past days".
    # If selected month is future, all days are "future days".
    
    last_day_of_selected_month = datetime(selected_year, selected_month, calendar.monthrange(selected_year, selected_month)[1]).date()
    first_day_of_selected_month = datetime(selected_year, selected_month, 1).date()

    days_in_month = len(dates)
    
    # Determine effective 'yesterday' for calculation
    # If selected month is in the past, all days are past.
    if last_day_of_selected_month < today:
        effective_yesterday = last_day_of_selected_month
    # If selected month is current month, 'yesterday' is actually yesterday.
    elif first_day_of_selected_month <= today <= last_day_of_selected_month:
        effective_yesterday = today - timedelta(days=1)
    # If selected month is in the future, no days are past yet (from perspective of 'today').
    else: # first_day_of_selected_month > today
        effective_yesterday = first_day_of_selected_month - timedelta(days=1) # No days are "past" yet

    past_days_count = sum(1 for d in dates if d <= effective_yesterday)
    future_days_count = days_in_month - past_days_count

    sum_of_balances_so_far = sum(
        balance for date, balance in zip(dates, daily_balances) if date <= effective_yesterday
    )
    
    current_sum_total = sum(daily_balances)
    current_adb = current_sum_total / days_in_month if days_in_month > 0 else 0

    total_required_balance_for_month = float(target_adb) * days_in_month
    remaining_balance_needed_for_target = total_required_balance_for_month - sum_of_balances_so_far
    
    required_avg_from_effective_today = 0
    if future_days_count > 0:
        required_avg_from_effective_today = remaining_balance_needed_for_target / future_days_count
    elif past_days_count == days_in_month : # Month has passed
        required_avg_from_effective_today = 0 # No future days to influence
    else: # future_days_count is 0 but month hasn't fully passed (e.g. last day of month)
        # This case needs careful handling, if it's the last day, the "today's balance" is what matters
        # For now, let's assume if future_days_count is 0, the ADB is set.
         required_avg_from_effective_today = 0


    # Determine "today's balance" for the suggestion
    # This should be the balance on the 'effective_today' or the first future day.
    effective_today_for_balance = effective_yesterday + timedelta(days=1)
    if effective_today_for_balance > last_day_of_selected_month: # If we are past the month
        todays_balance_for_suggestion = daily_balances[-1] if daily_balances else 0
    else:
        todays_balance_for_suggestion = next(
            (bal for date, bal in zip(dates, daily_balances) if date == effective_today_for_balance),
            daily_balances[past_days_count] if past_days_count < len(daily_balances) else (daily_balances[-1] if daily_balances else 0)
        )
    
    adjustment = 0
    if future_days_count > 0 : # Only suggest adjustment if there are future days
        adjustment = required_avg_from_effective_today - todays_balance_for_suggestion
    
    on_track = current_adb >= target_adb if past_days_count == days_in_month else (todays_balance_for_suggestion >= required_avg_from_effective_today if future_days_count > 0 else False)


    return {
        "sum_of_balances_so_far": sum_of_balances_so_far,
        "total_required_balance_for_month": total_required_balance_for_month,
        "remaining_balance_needed": remaining_balance_needed_for_target,
        "required_avg": required_avg_from_effective_today,
        "todays_balance": todays_balance_for_suggestion, # This is balance on effective_today_for_balance
        "adjustment": adjustment,
        "future_days": future_days_count,
        "past_days": past_days_count,
        "current_adb": current_adb,
        "days_in_month": days_in_month,
        "on_track_for_target": on_track,
        "effective_today_for_suggestion": effective_today_for_balance
    }


def plot_balances_streamlit(dates, balances, required_avg, target_adb, selected_year, selected_month):
    """Plot balance history and required average line for Streamlit."""
    if not dates or not balances:
        st.info("Not enough data to plot.")
        return None

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(dates, balances, label="Daily Balance", marker="o", linestyle="-", markersize=5)
    
    # Line for target ADB
    ax.axhline(y=target_adb, color='green', linestyle='--', label=f"Target ADB (${target_adb:,.2f})")

    # Line for required average from 'effective today'
    # This line should only be plotted for future days
    effective_today_date = datetime.today().date()
    # Adjust effective_today_date if selected month is not current month
    first_day_of_selected_month = datetime(selected_year, selected_month, 1).date()
    last_day_of_selected_month = datetime(selected_year, selected_month, calendar.monthrange(selected_year, selected_month)[1]).date()

    if first_day_of_selected_month > effective_today_date: # Selected month is in future
        plot_required_avg_from = first_day_of_selected_month
    elif last_day_of_selected_month < effective_today_date: # Selected month is in past
        plot_required_avg_from = None # Don't plot
    else: # Current month
        plot_required_avg_from = effective_today_date

    if plot_required_avg_from and required_avg > 0:
        # Find index of plot_required_avg_from in dates
        try:
            start_idx = dates.index(plot_required_avg_from)
            ax.plot(dates[start_idx:], [required_avg] * len(dates[start_idx:]), color='red', linestyle='--', label=f"Required Avg from {plot_required_avg_from.strftime('%b %d')} (${required_avg:,.2f})")
        except ValueError:
            # If plot_required_avg_from is not in dates (e.g., weekend, or outside month range for some reason)
            # We can try to find the closest date or just draw from the first future date.
            # For simplicity, if today is not in dates, we can find the first date >= today.
            future_dates_for_plot = [d for d in dates if d >= plot_required_avg_from]
            if future_dates_for_plot:
                 ax.plot(future_dates_for_plot, [required_avg] * len(future_dates_for_plot), color='red', linestyle='--', label=f"Required Avg from {future_dates_for_plot[0].strftime('%b %d')} (${required_avg:,.2f})")


    # Vertical line for 'today' if current month
    if first_day_of_selected_month <= datetime.today().date() <= last_day_of_selected_month:
        ax.axvline(x=datetime.today().date(), color='gray', linestyle=':', label="Today")

    ax.set_title(f"Daily Balances for {calendar.month_name[selected_month]} {selected_year} and ADB Target")
    ax.set_xlabel("Date")
    ax.set_ylabel("Balance ($)")
    
    # Format y-axis to show currency
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    
    plt.xticks(rotation=45)
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend()
    plt.tight_layout()
    return fig

# --- Streamlit App UI ---
st.set_page_config(layout="wide")
st.title("📈 Average Daily Balance (ADB) Calculator & Forecaster")

# Sidebar for inputs
st.sidebar.header("Configuration")

current_date = datetime.today()
# Ensure start_balance, target_adb are float, handle None from number_input if empty
start_balance = st.sidebar.number_input("Starting Balance (end of previous month)", value=100000.00, format="%.2f", step=1000.0)
target_adb = st.sidebar.number_input("Target ADB for the Month", value=100000.00, format="%.2f", step=1000.0)
selected_year = st.sidebar.number_input("Year", value=current_date.year, min_value=current_date.year - 5, max_value=current_date.year + 5, step=1)
selected_month = st.sidebar.number_input("Month (1-12)", value=current_date.month, min_value=1, max_value=12, step=1)

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
        # Process inputs
        transactions_dict = load_transactions_from_text(pasted_transactions)
        
        if isinstance(transactions_dict, defaultdict) and not dict(transactions_dict): # Error occurred in loading
             st.warning("Proceeding with calculation assuming no transactions due to previous error, or no transactions were input.")
             transactions_dict = {} # Ensure it's a plain dict for generate_daily_balances

        dates, daily_balances = generate_daily_balances(start_balance, transactions_dict, selected_year, selected_month)

        if not dates: # If generate_daily_balances failed (e.g. bad month)
            st.error("Could not generate daily balances. Please check year and month inputs.")
        else:
            results = calculate_adb_and_suggestion(dates, daily_balances, target_adb, selected_year, selected_month)

            st.header(f"ADB Analysis for {calendar.month_name[selected_month]} {selected_year}")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Target ADB", f"${target_adb:,.2f}")
            col2.metric("Current Calculated ADB", f"${results['current_adb']:,.2f}")
            
            if results['past_days'] == results['days_in_month']: # Month ended
                if results['current_adb'] >= target_adb:
                    col3.success(f"Met Target! Final ADB: ${results['current_adb']:,.2f}")
                else:
                    col3.error(f"Missed Target. Final ADB: ${results['current_adb']:,.2f}")
            elif results['current_adb'] >= results['required_avg'] and results['required_avg'] > 0 :
                 col3.success("On Track (Current ADB vs Req.)")
            elif results['required_avg'] > 0 :
                 col3.warning("Needs Attention")
            else: # required_avg is 0 (e.g. if no future days)
                 col3.info("Month not started or no future days.")


            st.subheader("📊 Key Figures")
            details_col1, details_col2 = st.columns(2)
            with details_col1:
                st.write(f"**Sum of balances up to 'effective yesterday' ({ (results['effective_today_for_suggestion'] - timedelta(days=1)).strftime('%Y-%m-%d') if results['days_in_month'] > 0 else 'N/A'}):** ${results['sum_of_balances_so_far']:,.2f}")
                st.write(f"**Total balance-days needed for target ADB:** ${results['total_required_balance_for_month']:,.2f}")
                st.write(f"**Remaining balance-days needed:** ${results['remaining_balance_needed']:,.2f}")
                st.write(f"**Days in month:** {results['days_in_month']}")
                st.write(f"**Past days (for calculation):** {results['past_days']}")
                st.write(f"**Remaining days (including 'effective today'):** {results['future_days']}")

            with details_col2:
                st.write(f"**Required average balance from 'effective today' ({results['effective_today_for_suggestion'].strftime('%Y-%m-%d') if results['days_in_month'] > 0 else 'N/A'}):** ${results['required_avg']:,.2f}")
                st.write(f"**Balance on 'effective today' ({results['effective_today_for_suggestion'].strftime('%Y-%m-%d') if results['days_in_month'] > 0 else 'N/A'}):** ${results['todays_balance']:,.2f}")

                if results['future_days'] > 0:
                    if results['adjustment'] > 0:
                        st.markdown(f"<h3 style='color: orange;'>💰 Suggest DEPOSIT of: ${results['adjustment']:,.2f} today/next business day</h3>", unsafe_allow_html=True)
                    elif results['adjustment'] < 0:
                        st.markdown(f"<h3 style='color: lightgreen;'>💸 Suggest WITHDRAWAL of: ${abs(results['adjustment']):,.2f} today/next business day</h3>", unsafe_allow_html=True)
                    else:
                        st.markdown("<h3 style='color: green;'>✅ No adjustment needed — on track to meet target ADB!</h3>", unsafe_allow_html=True)
                elif results['past_days'] == results['days_in_month']:
                    st.info("The selected month has ended. No further adjustments possible.")
                else:
                     st.info("No future days in the selected period to make adjustments, or calculations indicate no adjustment needed for the last day.")


            st.subheader("📈 Balance Trend")
            fig = plot_balances_streamlit(dates, daily_balances, results['required_avg'], target_adb, selected_year, selected_month)
            if fig:
                st.pyplot(fig)
            else:
                st.write("Could not generate plot.")
            
            if st.checkbox("Show Daily Balances Table"):
                import pandas as pd
                df_balances = pd.DataFrame({'Date': dates, 'Balance': daily_balances})
                df_balances['Date'] = pd.to_datetime(df_balances['Date']).dt.strftime('%Y-%m-%d (%a)')
                df_balances['Balance'] = df_balances['Balance'].map('${:,.2f}'.format)
                st.dataframe(df_balances, use_container_width=True)

else:
    st.info("ℹ️ Configure parameters in the sidebar and click 'Calculate ADB & Suggestion'.")
    st.markdown("""
    ### How to use:
    1.  **Starting Balance**: Enter your account balance as of the end of the day *before* the first day of the month you are analyzing.
    2.  **Target ADB**: Enter the Average Daily Balance you aim to achieve for the month.
    3.  **Year & Month**: Select the year and month for the analysis.
    4.  **Paste Transactions**:
        *   Paste your transactions in CSV (Comma Separated Values) format.
        *   The expected format for each line is `YYYY-MM-DD,amount`.
        *   Example: `2024-07-15,500.20` (for a deposit) or `2024-07-16,-120.00` (for a withdrawal).
        *   You can include a header row `date,amount` or paste data directly. The app tries to detect this.
        *   Blank lines or lines with `#` (comments) in the example are ignored.
    5.  Click **Calculate ADB & Suggestion**.

    The app will then display your projected daily balances, current ADB status, and a suggestion for deposits or withdrawals to meet your target.
    """)