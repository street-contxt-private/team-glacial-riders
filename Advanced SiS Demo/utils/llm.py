"""Set of functions providing extra LLM-based features based on Snowflake Cortex."""

import json
from typing import List, Optional, Tuple

import pandas as pd
import snowflake.cortex as cortex
from snowflake.snowpark.exceptions import SnowparkSQLException

from constants import (
    SMART_CHART_SUGGESTION_MODEL,
    SMART_DATA_SUMMARY_MODEL,
    SMART_FOLLOWUP_QUESTIONS_SUGGESTIONS_MODEL,
)
from utils.db import get_sf_connection
from utils.plots import (
    ALL_SUPPORTED_ARGS,
    AVAILABLE_CHARTS,
    ChartConfigDict,
    ChartDefinition,
    try_to_parse_raw_response_to_chart_cfg,
)


def get_question_suggestions(
    previous_question: str, semantic_model_desc: str, requested_suggestions: int = 3
) -> Tuple[List[str], Optional[str]]:
    """
    Generate follow-up questions based on the previous question asked by the user and the semantic model description.

    This function utilizes the Snowflake Cortex Compleate to generate follow-up questions that encourage the user
    to explore the data in more depth.

    Args:
        previous_question (str): The last question asked by the user.
        semantic_model_desc (str): The description of the underlying semantic model provided by the analyst.
        requested_suggestions (int, optional): The number of follow-up questions to generate. Defaults to 3.

    Returns:
        Tuple[List[str], Optional[str]]: A tuple containing a list of generated follow-up questions and an optional error message.
                                         If an error occurs, the list of suggestions will be empty and the error message will be provided.
    """
    session = get_sf_connection()
    prompt = f"""
You will suggest follow-up questions to the Business User who is interacting with data via Cortex Analyst - "Talk to your data" solution from Snowflake. Here is the description provided by Analyst on the underlying semantic model:
{semantic_model_desc}

The user's goal is to gain insights into underlying data. They have previously asked:
{previous_question}

Now generate {requested_suggestions} follow-up questions that encourage the user to explore the data in more depth. Do not include specific IDs or direct references to specific accounts or records in your suggestions. The tone should be formal and concise. Please provide questions that are precise and non-ambiguous.

Some examples of good follow-up questions might include: "What are the top 3 factors contributing to [specific trend]?" or "How does [specific variable] affect [outcome]?"

Output your answer as a JSON list of strings, like this:
["suggestion 1", "suggestion 2", "suggestion 3"]

Refrain from adding any other text before or after the generated list.
Here is the answer:
[
"""
    try:
        completion_response_raw = cortex.Complete(
            model=SMART_FOLLOWUP_QUESTIONS_SUGGESTIONS_MODEL,
            prompt=prompt,
            session=session,
            options=cortex.CompleteOptions(temperature=0.2),
        )
        completion_response_parsed = json.loads(completion_response_raw)
        # https://docs.snowflake.com/en/sql-reference/functions/complete-snowflake-cortex#returns
        parsed_sugggedtions = json.loads(
            completion_response_parsed["choices"][0]["messages"]
        )
    except SnowparkSQLException as e:
        err_msg = f"Error while generating suggestions thtough cortex.Complete: {e}"
        return [], err_msg
    except json.JSONDecodeError as e:
        err_msg = f"Error while parsing reponse from cortex.Compleate: {e}"
        return [], err_msg

    return parsed_sugggedtions, None


def get_results_summary(question: str, df: pd.DataFrame) -> Tuple[str, Optional[str]]:
    """
    Generate a concise summary of the data frame returned by Cortex Analyst in response to a user's question.

    Args:
        question (str): The question asked by the user.
        df (pd.DataFrame): The data frame generated by executing the SQL query returned by Cortex Analyst.

    Returns:
        Tuple[str, Optional[str]]: A tuple containing a concise summary. If an error occurs,
            the summary will be an empty string and the error message will be provided.
    """
    df_as_text = df.to_string(index=False)
    session = get_sf_connection()
    prompt = f"""
Provide a short summary for the data frame below, which was generated in response to the user's question: {question}.
The data frame is the result of executing the SQL query returned by Cortex Analyst.
Guide the user on how to interpret the results to answer their question and highlight any interesting key insights.

<RESULTS_BEGIN>
{df_as_text}
<RESULTS_END>

* Focus on delivering actionable insights that help the user understand the data and make informed decisions.
* Avoid unnecessary technical jargon and ensure the summary is easy to understand.
* Do not include specific IDs, account numbers, or other sensitive identifiers in the summary. Highlight trends, patterns, or aggregate insights instead.
* Provide a concise summary (2-4 sentences) with key insights, without any additional text or rewriting the question.
* Provide only the summary, nothing else, not even an opening sentence like "Here is the summary:"
* Escape any dollar signs ($) with a backslash (\\).
"""
    try:
        summary_response_raw = cortex.Complete(
            model=SMART_DATA_SUMMARY_MODEL, prompt=prompt, session=session
        )
    except SnowparkSQLException as e:
        err_msg = f"Error while generating suggestions thtough cortex.Complete: {e}"
        return "", err_msg
    return summary_response_raw, None


def _get_all_supported_params_instruction() -> str:
    all_instructions = []
    for chart_type, chart_def in AVAILABLE_CHARTS.values:
        chart: ChartDefinition = chart_def
        available_chart_options = f"type: {chart_type}"
        required_colum_params = (
            f"required column params: {', '.join(chart.base_column_args)}"
        )
        extra_column_params = (
            f"extra column parameters: {', '.join(chart.extra_column_args)}"
        )
        other_params = (
            f"other, non-column parameters: {', '.join(chart.extra_column_args)}"
        )
        all_instructions.append(
            f"""
{available_chart_options}
{required_colum_params}
{extra_column_params}
{other_params}
"""
        )
    return "\n\n".join(all_instructions)


def get_chart_suggestion(
    question: str, df: pd.DataFrame
) -> Tuple[Optional[ChartConfigDict], Optional[str]]:
    """Generate the best suitable config for given question and execution result."""
    df_as_text = df.to_string(index=False)
    session = get_sf_connection()
    prompt = f"""
Your task is to provide suggestion for the best possible chart answering the following question: {question}.
Here are results after running query which answers this question:

<RESULTS_BEGIN>
{df_as_text}
<RESULTS_END>

Your suggestion will take the form of JSON object representing plot config, in this format:
{{
    "type": <chart-type>,
    "<param-1>": "<param-1 value>",
    "<param-2>": "<param-2 value>",
    ...
}}
All params, beside first "type" key, represent plotly.express function arguments.
Here is the list of all types and params and plot functions supported by the whole system:
{_get_all_supported_params_instruction}

So if you would like to suggest pie-chart, with:
* "REGION" column as names
* "TOTAL_REVENUE" as values
you should output this:
{{
    "type": "Pie",
    "names": "REGION",
    "values": "TOTAL_REVENUE"
}}
Restrict yourself only to use those params:
{', '.join(ALL_SUPPORTED_ARGS.keys())}
Be aware that 'nbins' param must take numeric value, 'auto' is not allowed there.

Now generate your answer, do not add any additional text, only JSON object:
"""
    try:
        chart_suggestion_response_raw = cortex.Complete(
            model=SMART_CHART_SUGGESTION_MODEL, prompt=prompt, session=session
        )
        parsed_response = json.loads(chart_suggestion_response_raw)
    except SnowparkSQLException as e:
        err_msg = f"Error while generating suggestions thtough cortex.Complete: {e}"
        return None, err_msg
    except json.JSONDecodeError as e:
        err_msg = f"Error while parsing reponse from cortex.Compleate: {e}"
        return None, err_msg

    out_cfg, error = try_to_parse_raw_response_to_chart_cfg(
        parsed_response, set(df.columns)
    )
    if out_cfg is None:
        err_msg = f"Generated plot config is invalid: {error}"
        return None, err_msg

    return out_cfg, None
