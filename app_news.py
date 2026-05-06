import streamlit as st
import pandas as pd
import json
import re
from openai import OpenAI
from supabase import create_client, Client

# -------------------------------------------------------------------
# 1. 페이지 기본 설정
# -------------------------------------------------------------------
st.set_page_config(page_title="AI 뉴스 검색 및 저장소", page_icon="📰", layout="wide")

# .streamlit/secrets.toml 파일에 아래 3개 키가 정의되어 있어야 합니다.

# -------------------------------------------------------------------
# 2. 비밀 키(Secrets) 불러오기
# -------------------------------------------------------------------
# 실제 키 값을 입력하지 마세요! 이름표(st.secrets)만 적습니다.
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]  # 코드를 이렇게 수정하세요.
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# Supabase 클라이언트 연결
@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# OpenAI 클라이언트 연결
client = OpenAI(api_key=OPENAI_API_KEY)

# -------------------------------------------------------------------
# 3. 화면 UI 구성 (3개의 탭)[cite: 2]
# -------------------------------------------------------------------
st.title("📰 AI 최신 뉴스 검색 & 자동 저장기")
st.info("💡 안내: OpenAI GPT 모델을 사용하며, 검색 결과는 자동으로 Supabase 'news_history' 테이블에 저장됩니다.")

tab1, tab2, tab3 = st.tabs(["🔍 뉴스 검색 및 저장", "💾 저장된 뉴스 목록", "📊 분석 통계"])

# ==========================================
# 탭 1: 검색 및 자동 저장[cite: 1, 2]
# ==========================================
with tab1:
    st.subheader("새로운 뉴스 검색")
    keyword = st.text_input("검색할 뉴스 키워드를 입력하세요 (예: 반도체, 생성형 AI)")
    
    if st.button("뉴스 검색 및 자동 저장", type="primary"):
        if not keyword:
            st.warning("키워드를 입력해주세요!")
        else:
            with st.spinner("최신 뉴스를 검색하고 DB에 저장하는 중입니다..."):
                try:
                    # 1. GPT에 뉴스 검색 및 JSON 요약 요청
                    prompt = f"""
                    다음 키워드에 대한 가장 최신 뉴스 5건을 찾아 요약해주세요: '{keyword}'
                    반드시 아래 형태의 JSON 배열로만 출력하세요. 
                    다른 설명은 생략하세요.
                    [
                        {{
                            "title": "뉴스 제목",
                            "source": "언론사 이름",
                            "news_date": "YYYY-MM-DD",
                            "url": "https://...",
                            "summary": "3~4문장 요약"
                        }}
                    ]
                    """
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2
                    )
                    
                    # 2. 결과 추출 및 파싱
                    raw_text = response.choices[0].message.content
                    match = re.search(r'\[\s*\{.*?\}\s*\]', raw_text, re.DOTALL)
                    news_data = json.loads(match.group(0)) if match else []
                    
                    # 3. 화면 출력 및 DB 저장
                    saved_count = 0
                    duplicate_count = 0
                    
                    for news in news_data:
                        with st.container(border=True):
                            st.markdown(f"#### [{news.get('title')}]({news.get('url')})")
                            st.caption(f"🏢 {news.get('source')} | 📅 {news.get('news_date')}")
                            st.write(news.get('summary'))
                        
                        db_record = {
                            "keyword": keyword,
                            "title": news.get("title"),
                            "source": news.get("source"),
                            "news_date": news.get("news_date"),
                            "url": news.get("url"),
                            "summary": news.get("summary")
                        }
                        
                        try:
                            supabase.table("news_history").insert(db_record).execute()
                            saved_count += 1
                        except Exception as e:
                            if "duplicate" in str(e) or "23505" in str(e):
                                duplicate_count += 1
                    
                    st.toast(f"✅ 신규 저장: {saved_count}건 | 🔄 중복 제외: {duplicate_count}건")

                except Exception as e:
                    st.error(f"오류 발생: {e}")

# ==========================================
# 탭 2: 저장된 뉴스 보기[cite: 2]
# ==========================================
with tab2:
    st.subheader("🗄️ 데이터베이스 저장 목록")
    
    try:
        # DB에서 모든 데이터 최신순으로 가져오기
        res = supabase.table("news_history").select("*").order("created_at", desc=True).execute()
        db_data = res.data
        
        if db_data:
            df = pd.DataFrame(db_data)
            
            # 필터링 기능
            search_filter = st.text_input("목록 내 검색 (키워드 또는 제목)")
            if search_filter:
                df = df[df['keyword'].str.contains(search_filter, case=False) | 
                        df['title'].str.contains(search_filter, case=False)]
            
            # 데이터프레임 출력
            st.dataframe(
                df[["keyword", "title", "source", "news_date", "url", "created_at"]],
                use_container_width=True,
                hide_index=True
            )
            
            # CSV 다운로드[cite: 1]
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button("📥 CSV 데이터 다운로드", csv, "news_export.csv", "text/csv")
        else:
            st.info("저장된 데이터가 없습니다. 먼저 뉴스를 검색해 보세요.")
    except Exception as e:
        st.error(f"데이터 로드 중 오류: {e}")

# ==========================================
# 탭 3: 통계 분석[cite: 2]
# ==========================================
with tab3:
    st.subheader("📊 수집 데이터 통계")
    
    # 탭 2에서 가져온 db_data 재사용
    if 'db_data' in locals() and db_data:
        df_stats = pd.DataFrame(db_data)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**📌 주요 검색 키워드 순위**")
            key_counts = df_stats['keyword'].value_counts()
            st.bar_chart(key_counts)
            
        with col2:
            st.markdown("**📌 언론사별 수집 비중**")
            source_counts = df_stats['source'].value_counts()
            st.bar_chart(source_counts)
            
        st.markdown("**📌 날짜별 데이터 저장 추이**")
        df_stats['date_only'] = pd.to_datetime(df_stats['created_at']).dt.date
        date_trend = df_stats['date_only'].value_counts().sort_index()
        st.line_chart(date_trend)
    else:
        st.info("통계를 산출할 데이터가 없습니다.")
