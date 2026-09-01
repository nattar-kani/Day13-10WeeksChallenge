import psycopg
import json
from pymongo import MongoClient, UpdateOne


def get_postgres_connection():
    return psycopg.connect(
        host="postgres",
        port=5432,
        user="datapipe",
        password="datapipe_password",
        dbname="datapipe"
    )

def get_mongo_connection():
    client = MongoClient("mongodb://mongo:27017")
    return client

def create_db():
    with get_postgres_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    email TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    title TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS failed_records (
                    id SERIAL PRIMARY KEY,
                    source TEXT,
                    record TEXT,
                    error TEXT
                )
            """)

        conn.commit()


def insert_users(users):
    with get_postgres_connection() as conn:
        with conn.cursor() as cursor:

            for user in users:
                cursor.execute(
                    """
                    INSERT INTO users (id, name, email)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        user["id"],
                        user["name"],
                        user["email"]
                    )
                )

        conn.commit()


def insert_posts(posts):
    with get_postgres_connection() as conn:
        with conn.cursor() as cursor:

            for post in posts:
                cursor.execute(
                    """
                    INSERT INTO posts (id, user_id, title)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        post["id"],
                        post["user_id"],
                        post["title"]
                    )
                )

        conn.commit()


def insert_failed_records(records):
    with get_postgres_connection() as conn:
        with conn.cursor() as cursor:

            for record in records:
                cursor.execute(
                    """
                    INSERT INTO failed_records (source, record, error)
                    VALUES (%s, %s, %s)
                    """,
                    (
                        record["source"],
                        json.dumps(record["record"]),
                        record["error"]
                    )
                )

        conn.commit()

def insert_raw_data(users,posts):
    client = get_mongo_connection()
    db = client["datapipe"]

    users_coll = db["users_raw"]
    posts_coll = db["posts_raw"]

    if users:
        user_operations = [
            UpdateOne(
                {"id": user["id"]},
                {"$set": user},
                upsert=True                
            )
            for user in users
        ]
        users_coll.bulk_write(user_operations)
    if posts:
        post_operations = [
            UpdateOne(
                {"id": post["id"]},
                {"$set": post},
                upsert=True
            )
            for post in posts
        ]
        posts_coll.bulk_write(post_operations)
    client.close()