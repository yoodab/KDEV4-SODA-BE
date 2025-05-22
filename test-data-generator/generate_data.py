import mysql.connector
from faker import Faker
import csv
import time
import os
import random
from datetime import datetime, timedelta
import bcrypt # 👈 bcrypt 임포트 확인

# --- ⚙️ 설정값 (🚨 중요: 실제 값으로 변경하고, 보안에 유의하세요) ---
DB_CONFIG = {
    'host': 'soda-test-db.c9ios8o6srzw.ap-northeast-2.rds.amazonaws.com', # 제공해주신 RDS 주소
    'user': 'admin',  # 👈 실제 RDS 사용자 아이디 (확인됨)
    'password': 'rulerule12', # 👈 실제 RDS 비밀번호 (확인됨)
    'database': 'soda-test-db', # 👈 데이터를 넣을 DB 이름 (확인됨)
    'port': 3306,
    'allow_local_infile': True # LOAD DATA LOCAL INFILE 사용을 위해 클라이언트 측 허용
}

# Faker 초기화 (한국어 데이터 생성)
fake = Faker('ko_KR')

# 생성할 데이터 건수
NUM_COMPANIES = 2
NUM_MEMBERS_PER_COMPANY_AVG = 2 # 회사당 평균 멤버 수 (총 멤버 수는 NUM_COMPANIES * 이 값 근처)

# CSV 파일 경로
COMPANIES_CSV_PATH = 'companies_data.csv'
MEMBERS_CSV_PATH = 'members_data.csv'

# Enum 값들 (Java Enum 정의와 동일하게)
MEMBER_ROLES = ["ADMIN", "USER"]
MEMBER_STATUSES = ["AVAILABLE", "BUSY", "AWAY", "ON_VACATION"]


# --- 📝 테이블 컬럼명 정의 ---
COMPANY_COLUMNS = [
    'name', 'phone_number', 'owner_name', 'company_number', 'address', 'detail_address',
    'created_at', 'updated_at', 'is_deleted'
]
MEMBER_COLUMNS = [
    'name', 'auth_id', 'password', 'email', 'position', 'phone_number', 'role', 'company_id', 'member_status',
    'created_at', 'updated_at', 'is_deleted'
]


# --- 🏭 데이터 생성 함수 ---
def generate_companies_csv(num_records, file_path):
    print(f"Generating {num_records} companies data to '{file_path}'...")
    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        for _ in range(num_records):
            created_at_dt = fake.date_time_between(start_date="-1y", end_date="now")
            updated_at_dt = fake.date_time_between(start_date=created_at_dt, end_date="now")
            writer.writerow([
                fake.company(),
                fake.phone_number(),
                fake.name(),
                fake.bothify(text='###-##-#####'),
                fake.address(),
                fake.secondary_address() if random.choice([True, False]) else None,
                created_at_dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                updated_at_dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                False
            ])
    print(f"'{file_path}' generated successfully.")

def generate_members_csv(num_total_members, file_path, company_ids_list):
    print(f"Generating {num_total_members} members data to '{file_path}'...")
    if not company_ids_list:
        print("Error: No company IDs provided. Cannot generate members related to companies.")
        return

    generated_auth_ids = set()

    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        for _ in range(num_total_members):
            while True:
                auth_id = fake.user_name() + str(random.randint(1000, 9999))
                if auth_id not in generated_auth_ids:
                    generated_auth_ids.add(auth_id)
                    break

            created_at_dt = fake.date_time_between(start_date="-1y", end_date="now")
            updated_at_dt = fake.date_time_between(start_date=created_at_dt, end_date="now")

            # --- 👇 비밀번호 암호화 로직 수정/추가 ---
            raw_password = "password1234"  # 모든 사용자의 비밀번호를 "password1234"로 고정
            
            password_bytes = raw_password.encode('utf-8')
            salt = bcrypt.gensalt() 
            hashed_password_bytes = bcrypt.hashpw(password_bytes, salt)
            hashed_password_str = hashed_password_bytes.decode('utf-8')
            # --- 👆 비밀번호 암호화 로직 끝 ---

            writer.writerow([
                fake.name(),
                auth_id,
                hashed_password_str,  # 👈 암호화된 비밀번호 사용
                fake.unique.email(),
                fake.job() if random.choice([True, False]) else None,
                fake.phone_number() if random.choice([True, False]) else None,
                random.choice(MEMBER_ROLES),
                random.choice(company_ids_list),
                random.choice(MEMBER_STATUSES),
                created_at_dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                updated_at_dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                False
            ])
    print(f"'{file_path}' generated successfully.")


# --- 💾 CSV 파일을 DB에 적재하는 함수 ---
def load_csv_to_db(conn, table_name, csv_file_path, db_columns_for_load):
    cursor = conn.cursor()
    escaped_csv_file_path = csv_file_path.replace('\\', '\\\\')
    db_column_list_sql = f"({', '.join(db_columns_for_load)})"
    load_sql = f"""
        LOAD DATA LOCAL INFILE '{escaped_csv_file_path}'
        INTO TABLE {table_name}
        FIELDS TERMINATED BY ','
        ENCLOSED BY '"'
        LINES TERMINATED BY '\\n'
        {db_column_list_sql};
    """
    print(f"Loading data from '{csv_file_path}' into table '{table_name}'...")
    start_time = time.time()
    try:
        cursor.execute(load_sql)
        conn.commit()
        affected_rows = cursor.rowcount
        end_time = time.time()
        print(f"✅ Successfully loaded {affected_rows} rows into '{table_name}' in {end_time - start_time:.2f} seconds.")
    except mysql.connector.Error as err:
        print(f"❌ Error loading data into {table_name}: {err}")
        print(f"Executed SQL: {load_sql}")
        conn.rollback()
    finally:
        cursor.close()

# --- ▶️ 메인 실행 로직 ---
if __name__ == "__main__":
    conn_main = None
    try:
        print("Connecting to the database...")
        conn_main = mysql.connector.connect(**DB_CONFIG)
        cursor_main = conn_main.cursor()
        print("✅ Successfully connected to the database.")

        # (선택) 테이블 데이터 초기화
        # print("Truncating existing data (Members, then Companies)...")
        # cursor_main.execute("SET foreign_key_checks = 0;")
        # cursor_main.execute("TRUNCATE TABLE member;")
        # cursor_main.execute("TRUNCATE TABLE company;")
        # cursor_main.execute("SET foreign_key_checks = 1;")
        # conn_main.commit()
        # print("Existing data truncated.")

        generate_companies_csv(NUM_COMPANIES, COMPANIES_CSV_PATH)
        load_csv_to_db(conn_main, 'company', COMPANIES_CSV_PATH, COMPANY_COLUMNS)

        print("Fetching generated company IDs...")
        company_ids = []
        cursor_main.execute(f"SELECT id FROM company ORDER BY id DESC LIMIT {NUM_COMPANIES}")
        rows = cursor_main.fetchall()
        if rows:
            company_ids = [row[0] for row in rows]
            print(f"Fetched {len(company_ids)} company IDs.")
        else:
            print("⚠️ Warning: Could not fetch company IDs. Members might not be linked correctly.")

        if company_ids:
            num_total_members_to_generate = NUM_COMPANIES * NUM_MEMBERS_PER_COMPANY_AVG
            generate_members_csv(num_total_members_to_generate, MEMBERS_CSV_PATH, company_ids)
            load_csv_to_db(conn_main, 'member', MEMBERS_CSV_PATH, MEMBER_COLUMNS)
        else:
            print("Skipping member data generation as no company IDs were found.")

    except mysql.connector.Error as e:
        if e.errno == 1049:
            print(f"❌ Database connection error: Unknown database '{DB_CONFIG['database']}'. Please check DB_CONFIG.")
        elif e.errno == 1045:
            print(f"❌ Database connection error: Access denied for user '{DB_CONFIG['user']}'. Please check credentials.")
        elif e.errno == 1146:
             print(f"❌ Database error: Table doesn't exist. Error: {e}")
        else:
            print(f"❌ An SQL error occurred: {e}")
    except Exception as ex:
        print(f"❌ An unexpected error occurred: {ex}")
    finally:
        if conn_main and conn_main.is_connected():
            if 'cursor_main' in locals() and cursor_main:
                cursor_main.close()
            conn_main.close()
            print("Database connection closed.")