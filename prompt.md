#### 🎯 Task Overview
Your goal is to automate the lifecycle of converting Python code into an Airflow pipeline, validating and executing it, and monitoring its execution status. Follow the steps strictly and loop as necessary based on conditions.

#### ✅ Step-by-Step Instructions
1. Generate [Airflow DAG Pipeline](#pipelines-stages) in Python using the [Pipeline Specifications](#-pipeline-specifications-strict).
2. Save the generated pipeline to a file.
3. Rescan available pipelines, so Airflow is aware of this new pipeline
4. Validate the pipeline: if there are validation errors (ignore warinings), then fix the error, regenerate the code and get back to the step #2.
5. Test the pipeline: if there are errors (ignore warinings), then fix the error, regenerate the code and get back to the step #2.
6. Trigger the pipeline. 
7. Monitor execution status:
- If status is `success` → terminate execution and quit
- If status is `failed` → restart from Step 1.
- If status is `queued` or `running` → wait briefly and retry status check.

#### 📦 Pipeline Specifications (Strict)
Use only the following DAG configuration. Do not invent or infer additional parameters:
- `dag_id`: generated_nasdaq
- `start_date`: now - 3 seconds
- `catchup`: False
- `tags`: [`nasdaq`, `report`, `gemini-2.5-flash-preview-05-20`]

The pipeline must generate the report:
- The report should have dark background
- The report should be a static html file, store it at `/tmp/report/<report-timestamp>.html`

The report should have the following sections:
 - Executive summary
 - Plots for each ticker
 - Tables with data

#### Pipeline's stages:
- Read data from https://data.samarkanov.info/files/NASDAQ_20100401_30.txt. 
*Here's a couple of lines from this file:*
    ```
    <ticker>,<per>,<date>,<open>,<high>,<low>,<close>,<vol>
    AAME,I,201004011230,1.48,1.48,1.48,1.48,350
    AAME,I,201004011500,1.5,1.54,1.5,1.54,1330
    ```

- In parallel: filter these stocks from the file: AAPL, GOOG, ASML, AMZN
- Calculate moving average for each ticker
- Create report
