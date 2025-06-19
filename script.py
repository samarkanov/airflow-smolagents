import pandas as pd
import requests
import io
import matplotlib.pyplot as plt
import seaborn as sns
import base64
from datetime import datetime

# --- Constants ---
DATA_URL = "https://data.samarkanov.info/files/NASDAQ_20100401_30.txt"
COLUMN_NAMES = ["ticker", "per", "date", "open", "high", "low", "close", "vol"]
REPORT_FILENAME = "nasdaq_moving_average_report.html"

def read_nasdaq_data(url: str) -> pd.DataFrame:
    """
    Reads NASDAQ data from a given URL.

    The data is expected to be a CSV-like file with a header.
    Column names are predefined. The 'date' column is converted
    to datetime objects.

    Args:
        url (str): The URL of the data file.

    Returns:
        pd.DataFrame: A DataFrame containing the NASDAQ data,
                      or an empty DataFrame if reading fails.
    """
    try:
        # Use requests to handle potential network issues gracefully
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        # Use io.StringIO to treat the string content as a file
        data_io = io.StringIO(response.text)

        # Read the CSV data, skipping the header row (row 0)
        df = pd.read_csv(data_io, header=None, names=COLUMN_NAMES, skiprows=1)

        # --- Data Cleaning and Type Conversion ---
        # Convert the 'date' column to datetime objects
        df['date'] = pd.to_datetime(df['date'], format='%Y%m%d%H%M')

        # Ensure numeric columns are of the correct type
        numeric_cols = ['open', 'high', 'low', 'close', 'vol']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Drop rows with any NaN values that may have resulted from coercion
        df.dropna(inplace=True)

        print(f"Successfully read and processed {len(df)} records.")
        return df

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from URL: {e}")
    except Exception as e:
        print(f"An error occurred while processing the data: {e}")

    return pd.DataFrame()


def filter_by_ticker(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Filters a DataFrame to include records for a specific ticker.

    Args:
        df (pd.DataFrame): The input DataFrame.
        ticker (str): The stock ticker symbol to filter by.

    Returns:
        pd.DataFrame: A new DataFrame containing only the records for the
                      specified ticker.
    """
    return df[df['ticker'] == ticker].copy()


def calculate_moving_average(df: pd.DataFrame, window: int) -> pd.DataFrame:
    """
    Calculates the moving average for the 'close' price.

    Args:
        df (pd.DataFrame): The input DataFrame, expected to contain data
                           for a single ticker sorted by date.
        window (int): The number of ticks (periods) for the moving average.

    Returns:
        pd.DataFrame: The DataFrame with a new column 'MA_{window}' for
                      the moving average.
    """
    if 'close' not in df.columns:
        raise ValueError("DataFrame must contain a 'close' column.")
    if not isinstance(window, int) or window <= 0:
        raise ValueError("Window size must be a positive integer.")

    # Sort by date to ensure correct rolling calculation
    df_sorted = df.sort_values(by='date')
    ma_col_name = f'MA_{window}'
    df_sorted[ma_col_name] = df_sorted['close'].rolling(window=window).mean()
    return df_sorted


def generate_html_report(report_df: pd.DataFrame, tickers: list, window: int):
    """
    Generates an HTML report with data, summary, and plots.

    Args:
        report_df (pd.DataFrame): The DataFrame containing all data to be reported.
                                  Must include the moving average column.
        tickers (list): A list of tickers included in the report.
        window (int): The moving average window size used.
    """
    # --- Plot Generation ---
    plots = {}
    plt.style.use('dark_background')
    palette = sns.color_palette("hls", as_cmap=True)

    for ticker in tickers:
        ticker_df = report_df[report_df['ticker'] == ticker]
        if ticker_df.empty:
            continue

        fig, ax = plt.subplots(figsize=(12, 6))

        # Plot closing price and moving average
        ax.plot(ticker_df['date'], ticker_df['close'], label='Close Price', color='cyan', linewidth=1.5)
        ax.plot(ticker_df['date'], ticker_df[f'MA_{window}'], label=f'{window}-Tick MA', color='magenta', linestyle='--', linewidth=2)

        # Formatting the plot
        ax.set_title(f'Closing Price vs. {window}-Tick Moving Average for {ticker}', fontsize=16)
        ax.set_xlabel('Date and Time', fontsize=12)
        ax.set_ylabel('Price (USD)', fontsize=12)
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.3)
        fig.autofmt_xdate() # Auto-format date labels for better readability

        # Save plot to a base64 string
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', bbox_inches='tight')
        plt.close(fig)
        plots[ticker] = base64.b64encode(img_buffer.getvalue()).decode('utf-8')

    # --- HTML Generation ---
    report_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ticker_list_str = ", ".join(tickers)
    
    # Use to_html for better table formatting and add custom classes
    table_html = report_df.to_html(classes='styled-table', index=False, border=0)

    # Build plot sections
    plot_html_sections = ""
    for ticker, img_data in plots.items():
        plot_html_sections += f"""
        <div class="plot-container">
            <h2>Analysis for {ticker}</h2>
            <img src="data:image/png;base64,{img_data}" alt="Plot for {ticker}">
        </div>
        """

    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NASDAQ Moving Average Report - {report_date}</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
            body {{
                background-color: #121212;
                color: #e0e0e0;
                font-family: 'Roboto', sans-serif;
                line-height: 1.6;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 1200px;
                margin: 20px auto;
                padding: 20px;
                background-color: #1e1e1e;
                border-radius: 8px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.4);
            }}
            h1, h2 {{
                color: #ffffff;
                border-bottom: 2px solid #03dac6;
                padding-bottom: 10px;
            }}
            h1 {{
                font-size: 2.5em;
                text-align: center;
            }}
            .executive-summary, .data-section {{
                background-color: #2c2c2c;
                padding: 20px;
                border-radius: 8px;
                margin-top: 20px;
            }}
            .executive-summary p {{
                font-size: 1.1em;
            }}
            .plot-container {{
                text-align: center;
                margin-top: 30px;
            }}
            .plot-container img {{
                max-width: 100%;
                height: auto;
                border-radius: 8px;
                margin-top: 15px;
            }}
            .styled-table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
                font-size: 0.9em;
            }}
            .styled-table thead tr {{
                background-color: #03dac6;
                color: #121212;
                text-align: left;
                font-weight: bold;
            }}
            .styled-table th, .styled-table td {{
                padding: 12px 15px;
            }}
            .styled-table tbody tr {{
                border-bottom: 1px solid #333;
            }}
            .styled-table tbody tr:nth-of-type(even) {{
                background-color: #2a2a2a;
            }}
            .styled-table tbody tr:last-of-type {{
                border-bottom: 2px solid #03dac6;
            }}
            footer {{
                text-align: center;
                margin-top: 30px;
                font-size: 0.8em;
                color: #777;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>NASDAQ Stock Analysis Report</h1>
                <p style="text-align:center; color: #bbb;">Generated on: {report_date}</p>
            </header>

            <section class="executive-summary">
                <h2>Executive Summary</h2>
                <p>
                    This report provides a technical analysis of selected NASDAQ stocks based on data from April 1, 2010.
                    It focuses on the <strong>{window}-tick moving average</strong> to identify trends in closing prices.
                    The analysis covers the following tickers: <strong>{ticker_list_str}</strong>.
                </p>
            </section>

            <section class="plots">
                {plot_html_sections}
            </section>

            <section class="data-section">
                <h2>Complete Data with Moving Average</h2>
                {table_html}
            </section>

            <footer>
                <p>Report generated by Python Analytics Script.</p>
            </footer>
        </div>
    </body>
    </html>
    """
    
    with open(REPORT_FILENAME, "w", encoding='utf-8') as f:
        f.write(html_template)
    print(f"\nSuccessfully generated HTML report: '{REPORT_FILENAME}'")


def main():
    """
    Main function to run the data analysis and reporting pipeline.
    """
    # --- Configuration ---
    # We will analyze a few prominent tickers for demonstration
    TICKERS_TO_ANALYZE = ['AAPL', 'GOOG', 'MSFT', 'AMZN']
    MOVING_AVERAGE_WINDOW = 30  # e.g., 30-tick moving average

    print("--- Starting NASDAQ Data Analysis ---")

    # 1. Read data
    full_df = read_nasdaq_data(DATA_URL)

    if full_df.empty:
        print("Halting execution due to data reading failure.")
        return

    # 2. Filter and process data for selected tickers
    processed_dfs = []
    available_tickers = [t for t in TICKERS_TO_ANALYZE if t in full_df['ticker'].unique()]
    
    if not available_tickers:
        print("None of the selected tickers were found in the dataset.")
        print(f"Available tickers start with: {full_df['ticker'].unique()[:10]}")
        return

    print(f"\nFound data for: {', '.join(available_tickers)}")
    print(f"Calculating {MOVING_AVERAGE_WINDOW}-tick moving average for each...")

    for ticker in available_tickers:
        ticker_df = filter_by_ticker(full_df, ticker)
        ticker_df_with_ma = calculate_moving_average(ticker_df, window=MOVING_AVERAGE_WINDOW)
        processed_dfs.append(ticker_df_with_ma)

    # 3. Combine processed data into a single DataFrame for the report table
    report_df = pd.concat(processed_dfs)

    # 4. Generate the final HTML report
    generate_html_report(report_df, available_tickers, MOVING_AVERAGE_WINDOW)
    
    print("\n--- Analysis Complete ---")


if __name__ == "__main__":
    main()

