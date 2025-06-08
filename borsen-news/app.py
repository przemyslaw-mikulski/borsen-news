import streamlit as st
from fetch_and_translate import fetch_articles, translate_text
from db import save_to_db, load_latest, cleanup_old_articles, delete_all_articles
import duckdb
import os

# Initialize scheduler
try:
    from scheduler import get_scheduler
    scheduler_available = True
except ImportError:
    scheduler_available = False

st.title("📰 Børsen RSS Feed Explorer")

# Create main layout with columns
main_col, db_col = st.columns([3, 1])

with main_col:
    # Check if we're in a local environment with Mistral available
    try:
        import ollama
        # Try to list models to see if Mistral is available
        models = ollama.list()
        mistral_available = any('mistral' in model['name'] for model in models.get('models', []))
        if mistral_available:
            translate_options = ["none", "deepl", "openai", "mistral7b", "togetherai"]
        else:
            translate_options = ["none", "deepl", "openai", "togetherai"]
            st.info("💡 Mistral 7B (local) not available. Cloud options available: Together AI.")
    except (ImportError, Exception):
        translate_options = ["none", "deepl", "openai", "togetherai"]
        st.info("💡 Running in cloud environment. Mistral 7B available via Together AI.")
    
    translate_method = st.selectbox("Translate summaries to English using:", translate_options)

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

# Right-hand side database management panel
with db_col:
    with st.expander("🗄️ Database Management", expanded=False):
        # Show database statistics
        DB_PATH = "borsen.duckdb"
        if os.path.exists(DB_PATH):
            file_size_mb = round(os.path.getsize(DB_PATH) / (1024 * 1024), 2)
            st.metric("Database Size", f"{file_size_mb} MB")
            
            try:
                con = duckdb.connect(DB_PATH)
                total_articles = con.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
                st.metric("Total Articles", total_articles)
                con.close()
            except:
                st.metric("Total Articles", 0)
        else:
            st.info("Database not created yet")

        # Manual cleanup button
        if st.button("🧹 Clean Old Articles", key="cleanup_old"):
            deleted_count = cleanup_old_articles()
            if deleted_count > 0:
                st.success(f"Deleted {deleted_count} old articles")
            else:
                st.info("No articles older than 7 days found")

        # Clean all articles button with confirmation
        st.divider()
        if st.button("🗑️ Clean All Articles", type="secondary", key="delete_all"):
            if 'confirm_delete_all' not in st.session_state:
                st.session_state.confirm_delete_all = True
                st.rerun()

        if st.session_state.get('confirm_delete_all', False):
            st.warning("⚠️ This will delete ALL articles!")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("✅ Confirm", key="confirm_yes"):
                    deleted_count = delete_all_articles()
                    st.success(f"Deleted all {deleted_count} articles")
                    st.session_state.confirm_delete_all = False
                    st.rerun()
            
            with col2:
                if st.button("❌ Cancel", key="confirm_no"):
                    st.session_state.confirm_delete_all = False
                    st.rerun()

    # Auto-scheduler section in the same column
    if scheduler_available:
        with st.expander("🤖 Auto-Scheduler", expanded=False):
            scheduler = get_scheduler()
            status = scheduler.get_status()

            # Show scheduler status
            st.metric("Current Time (CET)", status["current_time"])
            if status["next_run"]:
                st.metric("Next Auto-Fetch", status["next_run"])

            # Scheduler controls
            col1, col2 = st.columns(2)
            with col1:
                if st.button("▶️ Start", key="start_scheduler", disabled=status["is_running"]):
                    if scheduler.start_scheduler():
                        st.success("✅ Auto-scheduler started!")
                        st.rerun()

            with col2:
                if st.button("⏸️ Stop", key="stop_scheduler", disabled=not status["is_running"]):
                    scheduler.stop_scheduler()
                    st.info("⏸️ Auto-scheduler stopped")
                    st.rerun()

            # Show scheduler stats
            if status["is_running"]:
                st.success("🟢 Auto-scheduler is RUNNING")
            else:
                st.info("🔴 Auto-scheduler is STOPPED")

            if status["last_fetch_time"]:
                st.text(f"Last fetch: {status['last_fetch_time']}")
                st.text(f"Status: {status['last_fetch_status']}")
                st.text(f"Total fetches: {status['fetch_count']}")

            st.info("📅 Every 30 min, 6am-8pm CET")
    else:
        with st.expander("🤖 Auto-Scheduler", expanded=False):
            st.warning("⚠️ Scheduler not available")
