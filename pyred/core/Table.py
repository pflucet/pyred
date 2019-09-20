import pandas as pd
import psycopg2

from pyred.core.Column import detect_type, find_sample_value


def get_table_info(_dbstream, table_and_schema_name):
    split = table_and_schema_name.split(".")
    if len(split) == 1:
        table_name = split[0]
        schema_name = None

    elif len(split) == 2:
        table_name = split[1]
        schema_name = split[0]
    else:
        raise Exception("Invalid table or schema name")
    query = "SELECT column_name, data_type, character_maximum_length, is_nullable FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='%s'" % table_name
    if schema_name:
        query = query + " AND TABLE_SCHEMA='%s'" % schema_name
    return _dbstream.execute_query(query)


def format_create_table(_dbstream, data):
    table_name = data["table_name"]
    columns_name = data["columns_name"]
    rows = data["rows"]
    params = {}
    df = pd.DataFrame(rows, columns=columns_name)
    df = df.where((pd.notnull(df)), None)
    for i in range(len(columns_name)):
        name = columns_name[i]
        example = find_sample_value(df, name, i)
        col = dict()
        col["example"] = example
        col["type"] = detect_type(_dbstream, name=name, example=example)
        params[name] = col

    query = """"""
    query = query + "CREATE TABLE " + table_name + " ("
    col = list(params.keys())
    for i in range(len(col)):
        k = col[i]
        string_example = " --example:" + str(params[k]["example"])[:10] + ''
        if i == len(col) - 1:
            query = query + "\n     " + k + ' ' + params[k]["type"] + ' ' + 'NULL ' + string_example
        else:
            query = query + "\n     " + k + ' ' + params[k]["type"] + ' ' + 'NULL ,' + string_example
    else:
        query = query[:-1]
    query = query + "\n )"
    print(query)
    return query


def create_table(_dbstream, data):
    query = format_create_table(_dbstream, data)
    try:
        _dbstream.execute_query(query)
    except psycopg2.ProgrammingError as e:
        e = str(e)
        if e[:7] == "schema ":
            _dbstream.execute_query("CREATE SCHEMA " + data['table_name'].split(".")[0])
            _dbstream.execute_query(query)
        else:
            print(e)


def create_columns(_dbstream, data, other_table_to_update):
    table_name = data["table_name"]
    rows = data["rows"]
    columns_name = data["columns_name"]
    infos = get_table_info(_dbstream, table_name)
    all_column_in_table = [e['column_name'] for e in infos]
    df = pd.DataFrame(rows, columns=columns_name)
    df = df.where((pd.notnull(df)), None)
    queries = []
    for column_name in columns_name:
        if column_name not in all_column_in_table:
            example = find_sample_value(df, column_name, columns_name.index(column_name))
            type_ = detect_type(_dbstream, name=column_name, example=example)
            query = """
            alter table %s
            add "%s" %s
            default NULL
            """ % (table_name, column_name, type_)
            queries.append(query)
            if other_table_to_update:
                query = """
                            alter table %s
                            add "%s" %s
                            default NULL
                            """ % (other_table_to_update, column_name, type_)
                queries.append(query)
    if queries:
        query = '; '.join(queries)
        _dbstream.execute_query(query)
    return 0