# filename: agents/quantitative.py

import os
import sqlite3
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

SCHEMA_CONTEXT = """

This database is SQLite. Generate ONLY SQLite-compatible SQL.
Do NOT use PostgreSQL functions such as DATE_TRUNC.
For grouping by month, use strftime('%Y-%m', date).
For grouping by year, use strftime('%Y', date).

If the request is a follow-up to a previous question, carry over any filters
from that question (time period, etc.) unless the user explicitly changes them.

Available tables:
- sales(id, region, product, revenue, date, units_sold)
- customers(id, name, industry, churn_date, satisfaction_score)
- employees(id, department, satisfaction_score, tenure_years)
"""


def validate_sql(query: str) -> dict:
    blocked = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]
    upper = query.upper()
    for word in blocked:
        if word in upper:
            return {"valid": False, "reason": f"Blocked keyword: {word}"}
    # Allow plain SELECT and CTEs (WITH ... SELECT); both are read-only.
    first = query.strip().upper()
    if not (first.startswith("SELECT") or first.startswith("WITH")):
        return {"valid": False, "reason": "Only SELECT/WITH queries are permitted"}
    return {"valid": True, "reason": "OK"}


def generate_sql(query: str, history_context: str = "") -> dict:
    response = client.chat.completions.create(
        model="gemini-3.5-flash-lite",
        max_tokens=768,
        temperature=0.2,
        messages=[{
            "role": "user",
            "content": f"{history_context}{SCHEMA_CONTEXT}\n\nGenerate a SQL query for: {query}\n\nReturn ONLY the SQL query, nothing else."
        }]
    )
    sql = response.choices[0].message.content.strip()
    # Gemini sometimes wraps SQL in markdown fences; strip them so validate_sql
    # sees a bare SELECT.
    if sql.startswith("```"):
        sql = sql.strip("`")                       # remove backticks
        if sql.lstrip().lower().startswith("sql"):
            sql = sql.lstrip()[3:]                 # remove leading "sql" tag
        sql = sql.strip()
    return {
        "sql": sql,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens
    }


def run(query: str, history_context: str = "") -> dict:
    sql_result = generate_sql(query, history_context)
    sql = sql_result["sql"]
    validation = validate_sql(sql)

    if not validation["valid"]:
        return {
            "answer": f"Query blocked: {validation['reason']}",
            "sql": sql,
            "rows": [],
            "validation": "FAILED",
            "input_tokens": sql_result["input_tokens"],
            "output_tokens": sql_result["output_tokens"]
        }

    try:
        conn = sqlite3.connect("./data/database.sqlite")
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        conn.close()

        # Use Gemini to interpret the results
        interpretation = client.chat.completions.create(
            model="gemini-3.5-flash-lite",
            max_tokens=512,
            temperature=0.2,
            messages=[{
                "role": "user",
                "content": f"The user asked: {query}\n\nSQL query used: {sql}\n\nResults:\nColumns: {cols}\nData: {rows[:20]}\n\nProvide a clear, concise interpretation of these results."
            }]
        )

        return {
            "answer": interpretation.choices[0].message.content,
            "sql": sql,
            "columns": cols,
            "rows": rows,
            "validation": "PASSED",
            "input_tokens": sql_result["input_tokens"] + interpretation.usage.prompt_tokens,
            "output_tokens": sql_result["output_tokens"] + interpretation.usage.completion_tokens
        }

    except Exception as e:
        return {
            "answer": f"Query execution failed: {str(e)}",
            "sql": sql,
            "rows": [],
            "validation": "ERROR",
            "input_tokens": sql_result["input_tokens"],
            "output_tokens": sql_result["output_tokens"]
        }
