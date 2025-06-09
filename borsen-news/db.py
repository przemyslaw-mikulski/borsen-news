import duckdb
import pandas as pd
from datetime import datetime, timedelta

DB_PATH = "borsen.duckdb"

def cleanup_old_articles():
    """Remove articles older than 7 days to keep storage costs low."""
    con = duckdb.connect(DB_PATH)
    cutoff_date = datetime.now() - timedelta(days=7)
    
    # Count articles before cleanup
    count_before = con.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    
    # Delete articles older than 7 days
    con.execute("DELETE FROM articles WHERE published < ?", [cutoff_date])
    
    # Count articles after cleanup
    count_after = con.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    deleted_count = count_before - count_after
    
    con.close()
    return deleted_count


def delete_all_articles():
    """Delete all articles from the database and reset it."""
    con = duckdb.connect(DB_PATH)

    # Count articles before deletion
    try:
        count_before = con.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    except:
        count_before = 0

    # Drop the entire table to completely empty the database
    con.execute("DROP TABLE IF EXISTS articles")

    # Recreate the table structure
    con.execute("""
        CREATE TABLE articles (
            title TEXT,
            summary TEXT,
            link TEXT,
            published TIMESTAMP,
            feed TEXT,
            translated_summary TEXT
        )
    """)

    con.close()
    return count_before


def save_to_db(df):
    """Save articles to database with duplicate prevention."""
    if df is None or len(df) == 0:
        return 0, 0, 0

    con = duckdb.connect(DB_PATH)
    try:
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

        # Get existing articles to check for duplicates
        try:
            existing_articles = con.execute("""
                SELECT title, summary, link FROM articles
            """).df()
        except:
            existing_articles = pd.DataFrame()

        if not existing_articles.empty:
            # Create a merged key for comparison (handle NaN values)
            existing_articles = existing_articles.fillna("")
            df_clean = df.fillna("")

            existing_keys = (existing_articles["title"].astype(str) + "|" +
                           existing_articles["summary"].astype(str) + "|" +
                           existing_articles["link"].astype(str))
            new_keys = (df_clean["title"].astype(str) + "|" +
                       df_clean["summary"].astype(str) + "|" +
                       df_clean["link"].astype(str))

            # Filter out duplicates
            mask = ~new_keys.isin(existing_keys)
            df_new = df[mask].copy()

            skipped_count = len(df) - len(df_new)
            added_count = 0

            if len(df_new) > 0:
                con.execute("INSERT INTO articles SELECT * FROM df_new")
                added_count = len(df_new)

        else:
            # No existing articles, insert all
            con.execute("INSERT INTO articles SELECT * FROM df")
            skipped_count = 0
            added_count = len(df)

    except Exception as e:
        print(f"Error saving to database: {e}")
        return 0, 0, 0
    finally:
        con.close()

    # Clean up old articles after saving new ones
    deleted_count = cleanup_old_articles()
    return deleted_count, skipped_count, added_count

def load_latest(n=50):
    con = duckdb.connect(DB_PATH)
    df = con.execute(f"SELECT * FROM articles ORDER BY published DESC LIMIT {n}").df()
    con.close()
    return df
