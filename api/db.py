import json

from django.db import connection


def _record(description, row):
    result = {}
    for column, value in zip(description, row):
        if value is not None and column.type_code in (114, 3802) and isinstance(value, str):
            value = json.loads(value)
        result[column.name] = value
    return result


def one(query, params=()):
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        row = cursor.fetchone()
        if row is None:
            return None
        return _record(cursor.description, row)


def all_rows(query, params=()):
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return [_record(cursor.description, row) for row in cursor.fetchall()]


def execute(query, params=()):
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.rowcount
