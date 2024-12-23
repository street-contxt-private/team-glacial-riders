import os

HOST = "qwb93411.us-east-1.snowflakecomputing.com"

# Api-related:
API_ENDPOINT = "/api/v2/cortex/analyst/message"
API_TIMEOUT = 30_000  # in miliseconds

# Very important to set those right:
# Path to app working schema
APP_SCHEMA_PATH = "HACKATHON_GLACIAL_RIDERS.PUBLIC"

# Name of the table where app saves information about saved queries
SAVED_QUERIES_TABLE_NAME = "SAVED_QUERIES"

# Local-dev specific:
DEV_SNOWPARK_CONNECTION_NAME = os.getenv(
    "SNOWPARK_CONNECTION_NAME", "sbx01"
)

# Enable/disable additional LLM-powered features:

# Followup questions in chat after each analyst reponse containing SQL
ENABLE_SMART_FOLLOWUP_QUESTIONS_SUGGESTIONS = True
SMART_FOLLOWUP_QUESTIONS_SUGGESTIONS_MODEL = "llama3.1-70b"

# Data summary after executing the query in chat
ENABLE_SMART_DATA_SUMMARY = True
SMART_DATA_SUMMARY_MODEL = "llama3-8b"

# Chart suggestions for data after executing the query in chat
ENABLE_SMART_CHART_SUGGESTION = True
SMART_CHART_SUGGESTION_MODEL = "mistral-large"
