import sqlite3
import json

def create_db():
    connection = sqlite3.connect("datapipe.db")
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT)""")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts(
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            title TEXT)""")    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS failed_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            record TEXT,
            error TEXT
        )
    """)    

    connection.commit()
    connection.close()

def insert_users(users):

    connection = sqlite3.connect("datapipe.db")
    cursor = connection.cursor()

    cursor.executemany(
        """
        INSERT INTO users (id, name, email)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
        name = excluded.name,
        email = excluded.email
        """,
        [
            (
                user["id"],
                user["name"],
                user["email"]
            )
            for user in users
        ]
    )

    connection.commit()
    connection.close()

def insert_posts(posts):

    connection = sqlite3.connect("datapipe.db")
    cursor = connection.cursor()

    cursor.executemany(
        """
        INSERT INTO posts (id, user_id, title)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
        user_id = excluded.user_id,
        title = excluded.title
        """,
        [
            (
                post["id"],
                post["user_id"],
                post["title"]
            )
            for post in posts
        ]
    )

    connection.commit()
    connection.close()

def insert_failed_records(records):

    connection = sqlite3.connect("datapipe.db")
    cursor = connection.cursor()

    cursor.executemany(
        """
        INSERT INTO failed_records (source, record, error)
        VALUES (?, ?, ?)
        """,
        [
            (
                record["source"],
                json.dumps(record["record"]),
                record["error"]
            )
            for record in records
        ]
    )

    connection.commit()
    connection.close()