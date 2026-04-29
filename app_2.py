import streamlit as st
import pandas as pd
from gnews import GNews
from newspaper import Article
import google.generativeai as genai
import io

# 1. 페이지 설정
st.set_page_config(page_title="최신 뉴스 요약기", page_icon="📰")

# 2. 사이드바에서 API 키 입력 받기
with st.sidebar:
    st.title("설정")
    api_key = st.text_input("Google API Key를 입력하세요", type="password")
    st.info("API 키는 Google AI Studio에서 발급받을 수 있습니다.")

# 3. Gemini 모델 설정 함수
def summarize_content(text, api_key):
    if not api_key:
        return "API 키가 필요합니다."
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(f"다음 뉴스 내용을 3문장 이내로 한국어로 요약해줘:\n\n{text}")
        return response.text
    except Exception as e:
        return f"요약 실패 (에러: {str(e)})"

# 4. 메인 화면 구성
st.title("📰 최신 뉴스 검색 & 요약기")
st.write("키워드를 입력하면 최신 뉴스 5개를 가져와 Gemini AI가 요약해 드립니다.")

query = st.text_input("검색할 뉴스 키워드를 입력하세요", placeholder="예: 삼성전자, 인공지능, K-POP")
search_button = st.button("뉴스 검색 및 요약 시작")

if search_button:
    if not api_key:
        st.error("먼저 사이드바에 Gemini API 키를 입력해주세요!")
    elif not query:
        st.warning("검색어를 입력해주세요.")
    else:
        with st.spinner("뉴스를 검색하고 요약 중입니다..."):
            # 뉴스 검색 설정 (한국어, 대한민국 지역, 최대 5개)
            google_news = GNews(language='ko', country='KR', max_results=5)
            news_results = google_news.get_news(query)
            
            if not news_results:
                st.error("검색 결과가 없습니다.")
            else:
                final_data = []
                
                for i, item in enumerate(news_results):
                    title = item['title']
                    url = item['url']
                    
                    # 기사 본문 추출 (newspaper3k 활용)
                    try:
                        article = Article(url, language='ko')
                        article.download()
                        article.parse()
                        content = article.text
                        
                        # 본문이 너무 짧으면 요약 대신 제목 사용
                        if len(content) < 100:
                            summary = summarize_content(f"제목: {title}", api_key)
                        else:
                            summary = summarize_content(content, api_key)
                    except Exception:
                        # 차단된 사이트나 오류 시 제목 기반으로 요약 시도
                        summary = summarize_content(f"제목: {title}. 이 뉴스 제목을 바탕으로 관련 내용을 간단히 설명해줘.", api_key)
                    
                    final_data.append({
                        "번호": i+1,
                        "제목": title,
                        "URL": url,
                        "요약내용": summary
                    })
                    
                    # 화면 표시
                    st.subheader(f"{i+1}. {title}")
                    st.write(f"🔗 [기사 원문 보기]({url})")
                    st.success(f"**요약:** {summary}")
                    st.divider()
                
                # 5. CSV 다운로드 기능
                df = pd.DataFrame(final_data)
                
                # CSV를 메모리 버퍼에 저장 (한글 깨짐 방지를 위해 utf-8-sig 사용)
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                csv_data = csv_buffer.getvalue()
                
                st.download_button(
                    label="검색 결과 CSV 다운로드",
                    data=csv_data,
                    file_name=f"{query}_뉴스_요약.csv",
                    mime="text/csv"
                )