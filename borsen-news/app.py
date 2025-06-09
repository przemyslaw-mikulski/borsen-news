import streamlit as st
import streamlit as st
import pandas as pd
from fetch_and_translate import fetch_articles, translate_text
from db import save_to_db, load_latest, cleanup_old_articles, delete_all_articles
import duckdb
import os

# Initialize scheduler
try:
    from scheduler import get_scheduler
    scheduler_available = True
    # Test scheduler creation to ensure it works
    test_scheduler = get_scheduler()
except ImportError as e:
    scheduler_available = False
except Exception as e:
    scheduler_available = False

st.title("📰 Børsen RSS Feed Explorer")

# Create main layout with columns
main_col, db_col = st.columns([3, 1])

with main_col:
    # Use Together AI for translation (hardcoded default)
    translate_method = "togetherai"

    # Create two columns for the fetch buttons
    col1, col2 = st.columns(2)
    
    with col1:
        fetch_articles_btn = st.button("🔄 Fetch latest articles")
    
    with col2:
        fetch_news_btn = st.button("📰 Fetch Latest News")

    if fetch_articles_btn or fetch_news_btn:
        df = fetch_articles()
        st.success(f"Fetched {len(df)} articles from the last 24 hours")
        
        # Always use Together AI for translation
        with st.spinner("Translating summaries..."):
            df["translated_summary"] = df["summary"].apply(lambda x: translate_text(x, translate_method))

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

    search_term = st.text_input("Search titles", "")
    articles_df = load_latest()

    if search_term:
        articles_df = articles_df[articles_df['title'].str.contains(search_term, case=False)]

    # Sort by published date descending
    articles_df = articles_df.sort_values('published', ascending=False)
    
    # Display the enhanced table with new columns including NÆVNTE sections
    if not articles_df.empty:
        # Select and reorder columns for display with the new NÆVNTE columns
        display_columns = ['title', 'translated_summary', 'naevnte_emner', 'naevnte_virksomheder', 'link', 'content', 'word_count', 'scraped_at', 'published']
        available_columns = [col for col in display_columns if col in articles_df.columns]
        
        # Format the dataframe for better display
        display_df = articles_df[available_columns].copy()
        
        # Keep links as plain URLs (clickable in Streamlit)
        if 'link' in display_df.columns:
            display_df['link'] = display_df['link'].apply(
                lambda x: x if pd.notna(x) else ""
            )
        
        # Truncate content for display
        if 'content' in display_df.columns:
            display_df['content'] = display_df['content'].apply(
                lambda x: f"{str(x)[:100]}..." if pd.notna(x) and len(str(x)) > 100 else str(x)
            )
        
        # Format scraped_at timestamp
        if 'scraped_at' in display_df.columns:
            display_df['scraped_at'] = pd.to_datetime(display_df['scraped_at']).dt.strftime('%Y-%m-%d %H:%M')
        
        # Format published timestamp  
        if 'published' in display_df.columns:
            display_df['published'] = pd.to_datetime(display_df['published']).dt.strftime('%Y-%m-%d %H:%M')
        
        st.dataframe(display_df, use_container_width=True, column_config={
            "link": st.column_config.Column(
                "Article Link",
                help="Click to open the full article",
                width="medium"
            ),
            "naevnte_emner": st.column_config.Column(
                "Mentioned Topics",
                help="Topics mentioned in the article",
                width="medium"
            ),
            "naevnte_virksomheder": st.column_config.Column(
                "Mentioned Companies",
                help="Companies mentioned in the article", 
                width="medium"
            )
        })
    else:
        st.info("No articles found. Click 'Fetch latest articles' to get the latest articles.")

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
    with st.expander("🤖 Auto-Scheduler", expanded=False):
        if scheduler_available:
            scheduler = get_scheduler()
            
            # Auto-start scheduler if not running
            if not scheduler.is_running:
                scheduler.start_scheduler()
            
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

                st.info("📅 Every 2 hours, 6am-12pm CET (with automatic translation)")
        else:
            st.warning("⚠️ Scheduler not available")
