import duckdb
import pandas as pd

DB_PATH = "borsen.duckdb"

def save_to_db(df):
    con = duckdb.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            title TEXT,
            summary TEXT,
            link TEXT,
            published TIMESTAMP,
            feed TEXT,
            translated_summary TEXT
        )
    """)
    
    # Check if feed column exists, if not add it
    try:
        con.execute("SELECT feed FROM articles LIMIT 1")
    except duckdb.CatalogException:
        con.execute("ALTER TABLE articles ADD COLUMN feed TEXT")
    
    # Check if translated_summary column exists, if not add it
    try:
        con.execute("SELECT translated_summary FROM articles LIMIT 1")
    except duckdb.CatalogException:
        con.execute("ALTER TABLE articles ADD COLUMN translated_summary TEXT")
    
    con.execute("INSERT INTO articles SELECT * FROM df")
    con.close()

def load_latest(n=50):
    con = duckdb.connect(DB_PATH)
    df = con.execute(f"SELECT * FROM articles ORDER BY published DESC LIMIT {n}").df()
    con.close()
    return df
