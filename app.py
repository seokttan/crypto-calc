import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import time
from datetime import datetime, timedelta
from streamlit_cookies_controller import CookieController
from curl_cffi import requests as requests_cffi

# --- [1] 세션 및 쿠키 설정 ---
controller = CookieController()

# yfinance 차단 우회를 위한 커스텀 세션 클래스
class CffiSession:
    def __init__(self):
        self.session = requests_cffi.Session(impersonate="chrome")
    def get(self, url, params=None, **kwargs):
        return self.session.get(url, params=params, **kwargs)

custom_session = CffiSession()

# --- [2] 데이터 로드 함수 (캐싱 적용) ---
@st.cache_data(ttl=3600) # 환율은 1시간만 유지
def get_exchange_rate():
    try:
        # yfinance 대신 직접 Yahoo Finance 데이터 페이지나 고정 API 호출
        # 방법 1: 가장 안정적인 인베스팅/야후 데이터 직접 요청 (curl_cffi 사용)
        url = "https://query1.finance.yahoo.com/v8/finance/chart/USDKRW=X?interval=1m&range=1d"
        
        # 브라우저인 척 위장하여 호출
        r = requests_cffi.Session(impersonate="chrome").get(url)
        data = r.json()
        
        # JSON 데이터에서 최신 종가 추출
        price = data['chart']['result'][0]['meta']['regularMarketPrice']
        return float(price)
    except Exception as e:
        # 에러 발생 시 로그 출력 및 기본값 반환
        st.error(f"환율 로드 실패: {e}")
        return 1400.0 # 실패 시 최근 평균 환율로 대체

def get_lbank_prices(coins):
    try:
        # LBank API 호출 (1초마다 실행되므로 타임아웃 짧게 설정)
        res = requests.get("https://api.lbkex.com/v2/ticker/24hr.do", params={'symbol': 'all'}, timeout=2).json()
        if res.get('result') == 'true':
            lbank_map = {item['symbol'].replace('_usdt', '').upper(): float(item['ticker']['latest']) for item in res['data']}
            return {coin: lbank_map.get(coin, 0.0) for coin in coins}
        return {coin: 0.0 for coin in coins}
    except:
        return {coin: 0.0 for coin in coins}

# --- [3] UI 레이아웃 설정 ---
st.set_page_config(page_title="Real-time Asset Sync", layout="centered")

# 쿠키에서 사용자 설정 불러오기
saved_coins = controller.get('my_target_coins')
if 'target_coins' not in st.session_state:
    # 쿠키가 있으면 쿠키값, 없으면 기본값
    st.session_state.target_coins = saved_coins if saved_coins else ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE']


# 입력 영역 (루프 밖)
with st.container():
    st.subheader("계산 기준 설정")
    c1, c2 = st.columns([1, 2])
    with c1:
        base_asset = st.selectbox("기준 자산", ["KRW", "USDT"] + st.session_state.target_coins)
    with c2:
        default_val = 1000000.0 if base_asset == "KRW" else 1.0
        input_val = st.number_input("수량/금액 입력", min_value=0.0, value=default_val, step=1.0)

# 실시간 갱신을 위한 placeholder
placeholder = st.empty()

# 자산 편집 영역 (하단 expander)
with st.expander("⚙️ 내 자산 리스트 편집 (쿠키 저장)"):
    add_col, del_col = st.columns(2)
    with add_col:
        new_coin = st.text_input("추가할 코인 심볼 (예: SOL)").upper().strip()
        if st.button("추가"):
            if new_coin and new_coin not in st.session_state.target_coins:
                st.session_state.target_coins.append(new_coin)
                controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                st.success(f"{new_coin} 추가됨")
                time.sleep(0.5)
                st.rerun()
    with del_col:
        if st.session_state.target_coins:
            del_coin = st.selectbox("삭제할 코인 선택", st.session_state.target_coins)
            if st.button("삭제"):
                st.session_state.target_coins.remove(del_coin)
                controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                st.warning(f"{del_coin} 삭제됨")
                time.sleep(0.5)
                st.rerun()

# --- [4] 1초 주기 실시간 루프 ---
while True:
    with placeholder.container():
        # 데이터 가져오기
        usd_to_krw = get_exchange_rate()
        coin_prices = get_lbank_prices(st.session_state.target_coins)
        
        # 한국 시간 계산 (UTC+9)
        kor_now = datetime.utcnow() + timedelta(hours=9)
        
        # 상단 지표
        st.caption(f"안전 모드 작동 중 (curl_cffi) | KST {kor_now.strftime('%H:%M:%S')}")
        st.metric("현재 환율 (USDKRW)", f"₩ {usd_to_krw:,.2f}")

        # 계산 로직
        if base_asset == "KRW":
            base_usdt = input_val / usd_to_krw
        elif base_asset == "USDT":
            base_usdt = input_val
        else:
            p_u = coin_prices.get(base_asset, 0.0)
            base_usdt = input_val * p_u if p_u > 0 else 0.0

        # 테이블 데이터 생성
        data = [
            ["KRW", "₩ 1.00", f"{base_usdt * usd_to_krw:,.0f}"],
            ["USDT", f"₩ {usd_to_krw:,.2f}", f"{base_usdt:,.2f}"]
        ]
        
        for coin in st.session_state.target_coins:
            p_u = coin_prices.get(coin, 0.0)
            p_k = p_u * usd_to_krw
            qty = base_usdt / p_u if p_u > 0 else 0.0
            data.append([coin, f"₩ {p_k:,.2f}", f"{qty:,.6f}"])

        # 데이터 프레임 출력 (인덱스 제거)
        df = pd.DataFrame(data, columns=["자산명", "시세(KRW)", "보유(계산)수량"])
        st.dataframe(df, use_container_width=True, hide_index=True)

    # 1초 대기
    time.sleep(1)
