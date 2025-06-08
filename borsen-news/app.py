import streamlit as st
from fetch_and_translate import fetch_articles, translate_text
from db import save_to_db, load_latest, cleanup_old_articles, delete_all_articles
import duckdb
import os

st.title("📰 Børsen RSS Feed Explorer")

# Sidebar for database management
st.sidebar.header("🗄️ Database Management")

# Show database statistics
DB_PATH = "borsen.duckdb"
if os.path.exists(DB_PATH):
    file_size_mb = round(os.path.getsize(DB_PATH) / (1024 * 1024), 2)
    st.sidebar.metric("Database Size", f"{file_size_mb} MB")
    
    try:
        con = duckdb.connect(DB_PATH)
        total_articles = con.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        st.sidebar.metric("Total Articles", total_articles)
        con.close()
    except:
        st.sidebar.metric("Total Articles", 0)
else:
    st.sidebar.info("Database not created yet")

# Manual cleanup button
if st.sidebar.button("🧹 Clean Old Articles"):
    deleted_count = cleanup_old_articles()
    if deleted_count > 0:
        st.sidebar.success(f"Deleted {deleted_count} old articles")
    else:
        st.sidebar.info("No articles older than 7 days found")

# Clean all articles button with confirmation
st.sidebar.divider()
if st.sidebar.button("🗑️ Clean All Articles", type="secondary"):
    if 'confirm_delete_all' not in st.session_state:
        st.session_state.confirm_delete_all = True
        st.rerun()

if st.session_state.get('confirm_delete_all', False):
    st.sidebar.warning("⚠️ This will delete ALL articles!")
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if st.button("✅ Confirm", key="confirm_yes"):
            deleted_count = delete_all_articles()
            st.sidebar.success(f"Deleted all {deleted_count} articles")
            st.session_state.confirm_delete_all = False
            st.rerun()
    
    with col2:
        if st.button("❌ Cancel", key="confirm_no"):
            st.session_state.confirm_delete_all = False
            st.rerun()

translate_method = st.selectbox("Translate summaries to English using:", ["none", "deepl", "openai", "mistral7b"])

if st.button("🔄 Fetch latest articles"):
    df = fetch_articles()
    st.success(f"Fetched {len(df)} articles from the last 24 hours")
    
    # Display articles immediately after fetching
    if len(df) > 0:
        st.subheader("📄 Fetched Articles")
        st.dataframe(df[['title', 'summary', 'link', 'published', 'feed']], use_container_width=True)
    
    if translate_method != "none":
        with st.spinner("Translating summaries..."):
            df["translated_summary"] = df["summary"].apply(lambda x: translate_text(x, translate_method))
    else:
        df["translated_summary"] = df["summary"].apply(lambda x: translate_text(x, "none"))
    
    try:
        deleted_count, skipped_count, added_count = save_to_db(df)
        
        # Show success message with details
        if translate_method != "none":
            st.success(f"Added {added_count} new articles with {translate_method} translations")
        else:
            st.success(f"Added {added_count} new articles (no translation applied)")
        
        if skipped_count > 0:
            st.info(f"⚠️ Skipped {skipped_count} duplicate articles")
        
        if deleted_count > 0:
            st.info(f"🧹 Cleaned up {deleted_count} articles older than 7 days to optimize storage")
            
    except Exception as e:
        st.error(f"Error saving articles to database: {e}")
        st.error("Please try again or contact support if the problem persists.")

st.subheader("🗂 Latest articles")

search_term = st.text_input("Search titles", "")
df = load_latest()

if search_term:
    df = df[df['title'].str.contains(search_term, case=False)]

st.dataframe(df[['title', 'translated_summary', 'link', 'published']], use_container_width=True)
