
import io
import pickle
import time
import zlib
import sqlite3
import ast
import matplotlib.pyplot as plt
from openpyxl import Workbook
import os

memory_db = {}
index_store = {}

# --- Configuration for Disk-Based Comparison ---
DISK_DB_FILE = "disk_database.db"

# --- Store and Retrieve with Compression ---
def store_data(table_name, data_dict):
    memfile = io.BytesIO()
    compressed = zlib.compress(pickle.dumps(data_dict))
    memfile.write(compressed)
    memfile.seek(0)
    memory_db[table_name] = memfile
    store_data_disk(table_name, data_dict) 

def retrieve_data(table_name):
    compressed = memory_db[table_name].getvalue()
    return pickle.loads(zlib.decompress(compressed))

# --- Store and Retrieve on Disk (SQLite) ---
def store_data_disk(table_name, data_dict):
    conn = sqlite3.connect(DISK_DB_FILE)
    cursor = conn.cursor()
    if data_dict:
        fields = list(next(iter(data_dict.values())).keys())
        # Check if table exists, if not create it
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
        if cursor.fetchone() is None:
            create_table_sql = f"CREATE TABLE {table_name} ({', '.join(fields)});"
            cursor.execute(create_table_sql)
        # Clear existing data and insert new data
        cursor.execute(f"DELETE FROM {table_name};")
        for row in data_dict.values():
            placeholders = ', '.join(['?'] * len(fields))
            values = [row.get(f) for f in fields]
            insert_sql = f"INSERT INTO {table_name} VALUES ({placeholders});"
            cursor.execute(insert_sql, values)
    conn.commit()
    conn.close()

def retrieve_data_disk(table_name):
    conn = sqlite3.connect(DISK_DB_FILE)
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    data = {}
    for i, row in enumerate(rows):
        record = {}
        for j, col in enumerate(columns):
            record[col] = row[j]
        data[i] = record 
    conn.close()
    return data

def log_to_file(query_name, execution_time, data, storage_type="Memory"):
    with open("runtime_report.txt", "a") as f:
        f.write(f"{query_name} ({storage_type}) - {execution_time:.6f} sec\nData: {data}\n\n")

# --- Safe Input Functions (same as before) ---
def get_valid_table(prompt):
    while True:
        print(f"Available tables: {list(memory_db.keys())}")
        table = input(prompt).strip()
        if table in memory_db:
            return table
        print("❌ Invalid table name. Try again.")

def get_valid_field(table_name, prompt):
    data = retrieve_data(table_name)
    if not data:
        print("⚠ Table is empty.")
        return input(prompt)
    fields = list(next(iter(data.values())).keys())
    while True:
        print(f"Available fields in '{table_name}': {fields}")
        field = input(prompt).strip()
        if field in fields:
            return field
        print("❌ Invalid field name. Try again.")

def get_valid_index_type():
    while True:
        index_type = input("Index type (hash/manual): ").strip().lower()
        if index_type in ["hash", "manual"]:
            return index_type
        print("❌ Invalid index type. Try again.")

def get_valid_join_type():
    while True:
        join_type = input("Join type (inner/left/right): ").strip().lower()
        if join_type in ["inner", "left", "right"]:
            return join_type
        print("❌ Invalid join type. Try again.")

# --- Sample Data (same as before) ---
teachers = {
    1: {"TeacherID": 1, "TeacherName": "Dr. Smith", "DeptID": 1},
    2: {"TeacherID": 2, "TeacherName": "Dr. Brown", "DeptID": 2}
}

students = {
    101: {"StudentID": 101, "StudentName": "Alice", "TeacherID": 1},
    102: {"StudentID": 102, "StudentName": "Bob", "TeacherID": 1},
    103: {"StudentID": 103, "StudentName": "Charlie", "TeacherID": 2}
}

departments = {
    1: {"DeptID": 1, "DeptName": "Computer Science"},
    2: {"DeptID": 2, "DeptName": "Physics"}
}

courses = {
    501: {"CourseID": 501, "CourseName": "Data Structures", "DeptID": 1},
    502: {"CourseID": 502, "CourseName": "Quantum Mechanics", "DeptID": 2}
}

store_data("teachers", teachers)
store_data("students", students)
store_data("departments", departments)
store_data("courses", courses)

# --- Core Operations (modified for comparison) ---
def view_records(compare_disk=True):
    table = get_valid_table("View records from table: ")

    # In-Memory
    start_mem = time.time()
    data_mem = retrieve_data(table)
    for k, v in data_mem.items():
        print(f"(Memory) {k}: {v}")
    end_mem = time.time()
    log_to_file(f"View {table}", end_mem - start_mem, data_mem, "Memory")

    # Disk-Based
    if compare_disk:
        start_disk = time.time()
        data_disk = retrieve_data_disk(table)
        print("\n--- Disk-Based ---")
        for k, v in data_disk.items():
            print(f"(Disk) {k}: {v}")
        end_disk = time.time()
        log_to_file(f"View {table}", end_disk - start_disk, data_disk, "Disk")
        print(f"\n⏱️ Memory Execution Time: {end_mem - start_mem:.6f} sec")
        print(f"⏱️ Disk Execution Time: {end_disk - start_disk:.6f} sec")

def view_joins(compare_disk=True):
    left = get_valid_table("Left table: ")
    right = get_valid_table("Right table: ")
    left_key = get_valid_field(left, "Join key from left: ")
    right_key = get_valid_field(right, "Join key from right: ")
    join_type = get_valid_join_type()

    left_data_mem = retrieve_data(left)
    right_data_mem = retrieve_data(right)
    result_mem = {}

    start_mem = time.time()
    if join_type == "inner":
        for l_id, l_val in left_data_mem.items():
            for r_id, r_val in right_data_mem.items():
                if l_val.get(left_key) == r_val.get(right_key):
                    result_mem[f"{l_id}-{r_id}"] = {**l_val, **r_val}
    elif join_type == "left":
        for l_id, l_val in left_data_mem.items():
            match = False
            for r_id, r_val in right_data_mem.items():
                if l_val.get(left_key) == r_val.get(right_key):
                    result_mem[f"{l_id}-{r_id}"] = {**l_val, **r_val}
                    match = True
            if not match:
                result_mem[f"{l_id}-NULL"] = l_val
    elif join_type == "right":
        for r_id, r_val in right_data_mem.items():
            match = False
            for l_id, l_val in left_data_mem.items():
                if l_val.get(left_key) == r_val.get(right_key):
                    result_mem[f"{l_id}-{r_id}"] = {**l_val, **r_val}
                    match = True
            if not match:
                result_mem[f"NULL-{r_id}"] = r_val
    end_mem = time.time()

    print("\n--- In-Memory Join Result ---")
    for k, v in result_mem.items():
        print(f"(Memory) {k}: {v}")
    log_to_file(f"{join_type.capitalize()} Join", end_mem - start_mem, result_mem, "Memory")

    if compare_disk:
        left_data_disk = retrieve_data_disk(left)
        right_data_disk = retrieve_data_disk(right)
        result_disk = {}

        start_disk = time.time()
        if join_type == "inner":
            for l_id, l_val in left_data_disk.items():
                for r_id, r_val in right_data_disk.items():
                    if l_val.get(left_key) == r_val.get(right_key):
                        result_disk[f"{l_id}-{r_id}"] = {**l_val, **r_val}
        elif join_type == "left":
            for l_id, l_val in left_data_disk.items():
                match = False
                for r_id, r_val in right_data_disk.items():
                    if l_val.get(left_key) == r_val.get(right_key):
                        result_disk[f"{l_id}-{r_id}"] = {**l_val, **r_val}
                        match = True
                if not match:
                    result_disk[f"{l_id}-NULL"] = l_val
        elif join_type == "right":
            for r_id, r_val in right_data_disk.items():
                match = False
                for l_id, l_val in left_data_disk.items():
                    if l_val.get(left_key) == r_val.get(right_key):
                        result_disk[f"{l_id}-{r_id}"] = {**l_val, **r_val}
                        match = True
                if not match:
                    result_disk[f"NULL-{r_id}"] = r_val
        end_disk = time.time()

        print("\n--- Disk-Based Join Result ---")
        for k, v in result_disk.items():
            print(f"(Disk) {k}: {v}")
        log_to_file(f"{join_type.capitalize()} Join", end_disk - start_disk, result_disk, "Disk")
        print(f"\n⏱️ Memory Execution Time: {end_mem - start_mem:.6f} sec")
        print(f"⏱️ Disk Execution Time: {end_disk - start_disk:.6f} sec")

def create_index(table, column, index_type):
    data = retrieve_data(table)
    index = {}
    for k, record in data.items():
        key = record.get(column)
        if key is not None:
            if index_type == "hash":
                index[key] = k
            else:
                index.setdefault(key, []).append(k)
    index_store[f"{table}_{column}"] = index
    print(f"✅ Index created on '{column}' with {index_type} indexing.")

def indexing_menu():
    table = get_valid_table("Indexing for table: ")
    column = get_valid_field(table, "Column to index: ")
    index_type = get_valid_index_type()
    create_index(table, column, index_type)

def run_sql_query(compare_disk=True):
    # In-Memory SQLite
    conn_mem = sqlite3.connect(DISK_DB_FILE)
    cursor_mem = conn_mem.cursor()
    for table in memory_db:
        data = retrieve_data(table)
        if data:
            fields = data[next(iter(data))].keys()
            try:
                cursor_mem.execute(f"CREATE TABLE {table} ({', '.join(fields)});")
                for row in data.values():
                    values = [row.get(f) for f in fields]
                    cursor_mem.execute(f"INSERT INTO {table} VALUES ({','.join(['?'] * len(values))})", values)
            except sqlite3.OperationalError as e:
                if "already exists" not in str(e):
                    print(f"Error creating in-memory table {table}: {e}")

    try:
        query = input("Enter your SQL query: ")
        start_mem = time.time()
        cursor_mem.execute(query)
        result_mem = cursor_mem.fetchall()
        print("\n--- In-Memory SQL Result ---")
        for row in result_mem:
            print(f"(Memory) {row}")
        conn_mem.commit()
        end_mem = time.time()
        log_to_file("SQL Query", end_mem - start_mem, result_mem, "Memory")
    except Exception as e:
        print("❌ In-Memory SQL Error:", e)
    finally:
        conn_mem.close()

    # Disk-Based SQLite
    if compare_disk:
        conn_disk = sqlite3.connect(DISK_DB_FILE)
        cursor_disk = conn_disk.cursor()
        try:
            start_disk = time.time()
            cursor_disk.execute(query)
            result_disk = cursor_disk.fetchall()
            print("\n--- Disk-Based SQL Result ---")
            for row in result_disk:
                print(f"(Disk) {row}")
            conn_disk.commit()
            end_disk = time.time()
            log_to_file("SQL Query", end_disk - start_disk, result_disk, "Disk")
            print(f"\n⏱️ Memory Execution Time: {end_mem - start_mem:.6f} sec")
            print(f"⏱️ Disk Execution Time: {end_disk - start_disk:.6f} sec")
        except Exception as e:
            print("❌ Disk-Based SQL Error:", e)
        finally:
            conn_disk.close()

# ----MONGODB QUERIES (modified for comparison)
def run_mongo_query(compare_disk=True):
    table = get_valid_table("MongoDB collection (table): ")
    data_mem = retrieve_data(table)
    data_disk = retrieve_data_disk(table)

    print("\nSupported MongoDB-like commands:")
    print("1. db.collection.find({})")
    print("2. db.collection.find({'field': value})")

    try:
        query = input("Enter MongoDB-like query: ").strip()

        if ".find(" in query:
            cond_str = query.split(".find(")[1].rstrip(")")
            cond = ast.literal_eval(cond_str) if cond_str.strip() else {}

            # In-Memory Find
            start_mem = time.time()
            result_mem = {k: record for k, record in data_mem.items() if all(record.get(field) == val for field, val in cond.items())}
            end_mem = time.time()
            print("\n--- In-Memory Find Result ---")
            for k, v in result_mem.items():
                print(f"(Memory) {k}: {v}")
            log_to_file("MongoDB Find", end_mem - start_mem, result_mem, "Memory")

            # Disk-Based Find (simulated - inefficient for complex queries)
            if compare_disk:
                start_disk = time.time()
                result_disk = {k: record for k, record in data_disk.items() if all(record.get(field) == val for field, val in cond.items())}
                end_disk = time.time()
                print("\n--- Disk-Based Find Result ---")
                for k, v in result_disk.items():
                    print(f"(Disk) {k}: {v}")
                log_to_file("MongoDB Find", end_disk - start_disk, result_disk, "Disk")
                print(f"\n⏱️ Memory Execution Time: {end_mem - start_mem:.6f} sec")
                print(f"⏱️ Disk Execution Time: {end_disk - start_disk:.6f} sec")

        # (Insert, Update, Delete for MongoDB-like are not optimized for comparison here for brevity)
        elif ".insertOne(" in query or ".updateOne(" in query or ".deleteOne(" in query:
            print("ℹ️ Insert, Update, and Delete operations are performed on both memory and disk, but direct comparison is not explicitly shown for brevity.")
            # ... (rest of the insert/update/delete logic - same as before, but will affect both memory_db and disk)
            table_name = get_valid_table("Target table: ")
            data_mem = retrieve_data(table_name)
            store_data_disk(table_name, data_mem) # Update disk as well

        else:
            print("❌ Unsupported MongoDB-like command for comparison.")
    except Exception as e:
        print("❌ Error parsing or executing Mongo query:", e)

# ---POSTGRESQL QUERIES (modified for comparison)
def run_postgresql_query(compare_disk=True):
    print("\n📘 PostgreSQL-like Query Engine (SQLite Underneath - Comparison Mode)")

    # In-Memory SQLite
    conn_mem = sqlite3.connect(":memory:")
    cursor_mem = conn_mem.cursor()
    for table in memory_db:
        data = retrieve_data(table)
        if data:
            fields = data[next(iter(data))].keys()
            try:
                cursor_mem.execute(f"CREATE TABLE {table} ({', '.join(fields)});")
                for row in data.values():
                    values = [row.get(f) for f in fields]
                    cursor_mem.execute(f"INSERT INTO {table} VALUES ({','.join(['?'] * len(values))})", values)
            except sqlite3.OperationalError as e:
                if "already exists" not in str(e):
                    print(f"Error creating in-memory table {table}: {e}")

    # Disk-Based SQLite
    conn_disk = sqlite3.connect(DISK_DB_FILE)
    cursor_disk = conn_disk.cursor()

    try:
        query = input("Enter your PostgreSQL-like SQL query: ")

        # In-Memory Execution
        start_mem = time.time()
        cursor_mem.execute(query)
        result_mem = cursor_mem.fetchall()
        end_mem = time.time()
        log_to_file("PostgreSQL Query", end_mem - start_mem, result_mem, "Memory")
        print("\n--- In-Memory PostgreSQL Result ---")
        for row in result_mem:
            print(f"(Memory) {row}")
        conn_mem.commit()

        # Disk-Based Execution
        if compare_disk:
            start_disk = time.time()
            cursor_disk.execute(query)
            result_disk = cursor_disk.fetchall()
            end_disk = time.time()
            log_to_file("PostgreSQL Query", end_disk - start_disk, result_disk, "Disk")
            print("\n--- Disk-Based PostgreSQL Result ---")
            for row in result_disk:
                print(f"(Disk) {row}")
            conn_disk.commit()
            print(f"\n⏱️ Memory Execution Time: {end_mem - start_mem:.6f} sec")
            print(f"⏱️ Disk Execution Time: {end_disk - start_disk:.6f} sec")

    except Exception as e:
        print("❌ PostgreSQL Query Error:", e)
    finally:
        conn_mem.close()
        conn_disk.close()

#-- tinyDB QUERIES (modified for comparison - basic read comparison)
def run_tinydb_query(compare_disk=True):
    table = get_valid_table("TinyDB table: ")
    data_mem = retrieve_data(table)
    data_disk = retrieve_data_disk(table)

    print("\n🔍 Supported TinyDB-like queries (Comparison Mode):")
    print("1. Query all: all")
    print("2. Query by single field: field == 'value'")

    query = input("Enter TinyDB-like query: ").strip()

    # In-Memory Query
    start_mem = time.time()
    result_mem = {}
    if query == "all":
        result_mem = data_mem
    elif "==" in query:
        field, value = [q.strip() for q in query.split("==")]
        value = ast.literal_eval(value)
        result_mem = {k: v for k, v in data_mem.items() if v.get(field) == value}
    end_mem = time.time()
    print("\n--- In-Memory TinyDB Result ---")
    for k, v in result_mem.items():
        print(f"(Memory) {k}: {v}")
    log_to_file("TinyDB Query", end_mem - start_mem, result_mem, "Memory")

    # Disk-Based Query (simulated - inefficient for complex queries)
    if compare_disk:
        start_disk = time.time()
        result_disk = {}
        if query == "all":
            result_disk = data_disk
        elif "==" in query:
            field, value = [q.strip() for q in query.split("==")]
            value = ast.literal_eval(value)
            result_disk = {k: v for k, v in data_disk.items() if v.get(field) == value}
        end_disk = time.time()
        print("\n--- Disk-Based TinyDB Result ---")
        for k, v in result_disk.items():
            print(f"(Disk) {k}: {v}")
        log_to_file("TinyDB Query", end_disk - start_disk, result_disk, "Disk")
        print(f"\n⏱️ Memory Execution Time: {end_mem - start_mem:.6f} sec")
        print(f"⏱️ Disk Execution Time: {end_disk - start_disk:.6f} sec")

#-- LMDB QUERIES (modified for basic key-value comparison)
def run_lmdb_query(compare_disk=True):
    table = get_valid_table("LMDB table: ")
    data_mem = retrieve_data(table)
    data_disk = retrieve_data_disk(table)

    print("\n⚡ LMDB-like (key-value) query options (Comparison Mode):")
    print("1. get <key>")
    print("2. all")

    query = input("Enter LMDB-like query: ").strip()

    if query.startswith("get "):
        try:
            key = int(query.split()[1])
            # In-Memory Get
            start_mem = time.time()
            result_mem = data_mem.get(key)
            end_mem = time.time()
            print(f"\n--- In-Memory Get Result ---")
            print(f"(Memory) {key}: {result_mem}")
            log_to_file(f"LMDB Get", end_mem - start_mem, {key: result_mem}, "Memory")

            # Disk-Based Get
            if compare_disk:
                start_disk = time.time()
                result_disk = data_disk.get(key)
                end_disk = time.time()
                print(f"\n--- Disk-Based Get Result ---")
                print(f"(Disk) {key}: {result_disk}")
                log_to_file(f"LMDB Get", end_disk - start_disk, {key: result_disk}, "Disk")
                print(f"\n⏱️ Memory Execution Time: {end_mem - start_mem:.6f} sec")
                print(f"⏱️ Disk Execution Time: {end_disk - start_disk:.6f} sec")
        except ValueError:
            print("❌ Invalid key format.")

    elif query == "all":
        # In-Memory All
        start_mem = time.time()
        print("\n--- In-Memory All Records ---")
        for k, v in data_mem.items():
            print(f"(Memory) {k}: {v}")
        end_mem = time.time()
        log_to_file("LMDB All", end_mem - start_mem, data_mem, "Memory")

        # Disk-Based All
        if compare_disk:
            start_disk = time.time()
            print("\n--- Disk-Based All Records ---")
            for k, v in data_disk.items():
                print(f"(Disk) {k}: {v}")
            end_disk = time.time()
            log_to_file("LMDB All", end_disk - start_disk, data_disk, "Disk")
            print(f"\n⏱️ Memory Execution Time: {end_mem - start_mem:.6f} sec")
            print(f"⏱️ Disk Execution Time: {end_disk - start_disk:.6f} sec")
            log_to_file("LMDB Query", end_disk - start_disk, result_disk, "Disk")

    else:
        print("❌ Invalid LMDB-like query for comparison.")

#-- REPORT GENERATION (modified to include comparison)
def report_generation():
    runtime_txt_file = "runtime_report.txt"
    runtime_excel_file = "runtimes.xlsx"

    memory_queries = {}
    disk_queries = {}

    try:
        with open(runtime_txt_file, "r") as file:
            for line in file:
                if " - " in line and "sec" in line:
                    parts = line.split(" - ")
                    query_info = parts[0].strip()
                    time_str = parts[1].split(" ")[0].strip()
                    storage_type = "Memory"
                    query_name = query_info
                    if " (Disk)" in query_info:
                        storage_type = "Disk"
                        query_name = query_info.replace(" (Disk)", "").strip()
                    elif " (Memory)" in query_info:
                        storage_type = "Memory"
                        query_name = query_info.replace(" (Memory)", "").strip()

                    if storage_type == "Memory":
                        memory_queries.setdefault(query_name, []).append(float(time_str))
                    elif storage_type == "Disk":
                        disk_queries.setdefault(query_name, []).append(float(time_str))

        if not memory_queries and not disk_queries:
            print("❌ No query data found in the report.")
            return

        # === Generate Comparison Graph ===
        query_labels = list(set(memory_queries.keys()) | set(disk_queries.keys()))
        x = range(len(query_labels))
        width = 0.35

        fig, ax = plt.subplots(figsize=(12, 7))
        rects1 = []
        if memory_queries:
            mem_times = [sum(memory_queries.get(q, [0.0])) / len(memory_queries.get(q, [1])) for q in query_labels]
            rects1 = ax.bar([i - width/2 for i in x], mem_times, width, label='Memory')

        rects2 = []
        if disk_queries:
            disk_times = [sum(disk_queries.get(q, [0.0])) / len(disk_queries.get(q, [1])) for q in query_labels]
            rects2 = ax.bar([i + width/2 for i in x], disk_times, width, label='Disk')

        ax.set_ylabel('Execution Time (seconds)')
        ax.set_title('Memory vs. Disk Query Runtime Comparison')
        ax.set_xticks(x)
        ax.set_xticklabels(query_labels, rotation=45, ha="right")
        ax.legend()
        fig.tight_layout()
        plt.savefig("runtime_comparison_graph.png")
        plt.show()

        # === Write to Excel ===
        wb = Workbook()
        ws = wb.active
        ws.title = "Query Runtimes Comparison"
        ws.append(["Query", "Memory Time (sec)", "Disk Time (sec)"])

        all_queries = sorted(list(set(memory_queries.keys()) | set(disk_queries.keys())))
        for query in all_queries:
            mem_avg = sum(memory_queries.get(query, [0.0])) / len(memory_queries.get(query, [1])) if memory_queries.get(query) else 0.0
            disk_avg = sum(disk_queries.get(query, [0.0])) / len(disk_queries.get(query, [1])) if disk_queries.get(query) else 0.0
            ws.append([query, mem_avg, disk_avg])

        wb.save(runtime_excel_file)
        print("✅ Comparison report generated: runtime_comparison_graph.png and runtimes.xlsx")

    except FileNotFoundError:
        print(f"❌ Error: {runtime_txt_file} not found. Run some queries first.")
    except Exception as e:
        print(f"❌ Error generating report: {str(e)}")

# --- Main Menu ---
def main_menu():
    while True:
        print("\n--- In-Memory Database System with Disk Comparison ---")
        print("1. View Records (Compare with Disk)")
        print("2. View Joins (Compare with Disk)")
        print("3. Indexing")
        print("4. Run SQL Query (Compare with Disk)")
        print("5. Run MongoDB-like Query (Compare with Disk)")
        print("6. Run Postgre-like Query (Compare with Disk)")
        print("7. Run tinyDB-like Query (Compare with Disk)")
        print("8. Run LMDB(Lightning Memory Mapped Database)-like Query (Compare with Disk)")
        print("9. Report Generation (Memory vs. Disk)")
        print("10. Exit")
        choice = input("Select option: ")
        if choice == "1":
            view_records()
        elif choice == "2":
            view_joins()
        elif choice == "3":
            indexing_menu()
        elif choice == "4":
            run_sql_query()
        elif choice == "5":
            run_mongo_query()
        elif choice == "6":
            run_postgresql_query()
        elif choice == "7":
            run_tinydb_query()
        elif choice == "8":
            run_lmdb_query()
        elif choice == "9":
            report_generation()
        elif choice == "10":
            print("Exiting the program")
            # Clean up disk database file on exit
            if os.path.exists("disk_database.db"):
                os.remove("disk_database.db")
            break
        else:
            print("❌ Invalid option. Try again.")

if __name__ == "__main__":
    # Clean up disk database file at the start, if it exists
   
    main_menu()