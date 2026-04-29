import os           # 환경변수(컴퓨터에 저장된 비밀값) 읽기용
import json         # 모델이 보내준 JSON 응답 해석용
import re           # 정규식: 응답에서 [...] 부분만 추출용
from datetime import datetime   # CSV 파일명에 시각 붙이기용
import streamlit as st          # 웹화면 만드는 도구
import pandas as pd             # 표 데이터를 다루고 CSV로 내보내기
from google import genai        # 새 Gemini SDK (옛 google-generativeai 아님!)
from google.genai import types  # GoogleSearch 도구 정의용

# ──────────────────────────────────────────────────────────────
# 1. Streamlit 페이지 기본 설정
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Gemini 뉴스검색기",   # 브라우저 탭에 보이는 이름
    page_icon="📰",                   # 탭 아이콘
    layout="centered",               # 화면 가운데 정렬
)

st.title("📰 Gemini 뉴스 검색기")
st.caption("Google Search Grounding을 활용한 실시간 뉴스 큐레이션")

# ──────────────────────────────────────────────────────────────
# 2. API 키 가져오기 함수
# ──────────────────────────────────────────────────────────────
def get_api_key() -> str:
    # 환경변수에서 키 읽기 (없으면 None 반환)
    api_key = os.environ.get("GEMINI_API_KEY")
    # 키가 비어있다면 등록 방법까지 자세히 안내
    if not api_key:
        st.error("⚠️ **GEMINI_API_KEY 가 설정되지 않았습니다.**")
        st.markdown("""
**설정 방법 (GitHub Codespaces):**
1. GitHub 저장소 → **Settings** → **Secrets and variables** → **Codespaces**
2. **New secret** 클릭
3. Name: `GEMINI_API_KEY` / Value: 발급받은 API 키 입력
4. Codespace를 **재시작**하면 적용됩니다.
        """)
        st.stop()  # 여기서 앱 실행 중단
    return api_key

# ──────────────────────────────────────────────────────────────
# 3. Gemini API로 뉴스 검색하는 함수
# ──────────────────────────────────────────────────────────────
def search_news_with_gemini(keyword: str) -> list[dict]:
    # ─── 1) Gemini 클라이언트 생성 (새 SDK 방식) ───────────────
    client = genai.Client(api_key=get_api_key())

    # ─── 2) Google Search 도구 정의 (실시간 웹검색 활성화) ──────
    grounding_tool = types.Tool(google_search=types.GoogleSearch())

    # ─── 3) 모델에게 보낼 한국어 프롬프트 ──────────────────────
    prompt = f"""당신은 뉴스 큐레이션 전문가입니다.
아래 키워드와 관련된 가장 최신의 뉴스 기사 5건을 Google 검색으로 찾아주세요.

키워드: "{keyword}"

각 기사에 대해 다음 정보를 **JSON 배열 형식으로만** 응답하세요.
설명, 인사말, 머리말, 코드블록(```)은 절대 포함하지 마세요.
응답은 오직 [ ... ] 로 시작하고 끝나는 순수한 JSON 배열이어야 합니다.

JSON 형식 예시:
[
  {{
    "title": "기사 제목",
    "source": "언론사 이름",
    "published_date": "2026-04-29",
    "url": "https://원본기사주소",
    "summary": "기사 핵심 내용을 한국어 3~4문장으로 요약"
  }}
]

규칙:
- 정확히 5건을 반환할 것
- url 은 실제 기사 원본 URL (구글 검색 결과 페이지 URL 금지)
- summary 는 반드시 한국어로 3~4문장
- published_date 는 YYYY-MM-DD 형식
- 가능한 한 최근 (최근 7일 이내) 기사 우선
"""

    # ─── 4) Gemini 호출 ─────────────────────────────────────────
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[grounding_tool],
            temperature=1.0,   # Search Grounding 사용 시 Google 권장값
        ),
    )

    # ─── 5) 응답 텍스트에서 JSON만 추출 ─────────────────────────
    text = (response.text or "").strip()

    # 모델이 ```json ... ``` 으로 감싸 보내는 경우 제거
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # [ ... ] 배열 부분만 추출
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        st.error("응답에서 JSON 배열을 찾을 수 없습니다. 다시 시도해주세요.")
        st.code(text, language="text")
        return []

    articles = json.loads(match.group())
    return articles

# ──────────────────────────────────────────────────────────────
# 4. 메인 UI
# ──────────────────────────────────────────────────────────────
keyword = st.text_input(
    "🔍 검색 키워드를 입력하세요",
    placeholder="예: 인공지능, 반도체, 기후변화 ...",
)

search_btn = st.button("뉴스 검색", type="primary", use_container_width=True)

if search_btn:
    if not keyword.strip():
        st.warning("키워드를 입력해주세요.")
    else:
        with st.spinner(f"**{keyword}** 관련 최신 뉴스를 검색 중입니다..."):
            try:
                articles = search_news_with_gemini(keyword.strip())
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")
                articles = []

        if articles:
            st.success(f"✅ {len(articles)}건의 뉴스를 찾았습니다.")
            st.divider()

            # ─── 기사 카드 출력 ──────────────────────────────────
            for i, article in enumerate(articles, 1):
                with st.container(border=True):
                    st.markdown(f"### {i}. [{article.get('title', '제목 없음')}]({article.get('url', '#')})")
                    col1, col2 = st.columns(2)
                    col1.caption(f"🗞️ {article.get('source', '출처 미상')}")
                    col2.caption(f"📅 {article.get('published_date', '날짜 미상')}")
                    st.write(article.get("summary", "요약 없음"))

            st.divider()

            # ─── CSV 다운로드 버튼 ───────────────────────────────
            df = pd.DataFrame(articles)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_data = df.to_csv(index=False, encoding="utf-8-sig")

            st.download_button(
                label="⬇️ 결과를 CSV로 다운로드",
                data=csv_data,
                file_name=f"news_{keyword}_{timestamp}.csv",
                mime="text/csv",
                use_container_width=True,
            )
