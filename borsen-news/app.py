import streamlit as st
from fetch_and_translate import fetch_articles, translate_text
from db import save_to_db, load_latest

st.title("📰 Børsen RSS Feed Explorer")

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
        df["translated_summary"] = df["summary"]
    save_to_db(df)
    st.success(f"Articles saved to database with translations")

st.subheader("🗂 Latest articles")

search_term = st.text_input("Search titles", "")
df = load_latest()

if search_term:
    df = df[df['title'].str.contains(search_term, case=False)]

st.dataframe(df[['title', 'translated_summary', 'link', 'published']], use_container_width=True)
