import streamlit as st
import requests
import yfinance as yf
import pandas as pd
import time
from streamlit_cookies_controller import CookieController

# --- 쿠키 컨트롤러 초기화 ---
controller = CookieController()

# --- 데이터 가져오기 함수 ---
@st.cache_data(ttl=60)
def get_market_data(coins):
    try:
        fx = yf.Ticker("USDKRW=X").history(period="1d")['Close'].iloc[-1]
        res = requests.get("https://api.lbkex.com/v2/ticker/24hr.do", params={'symbol': 'all'}).json()
        prices = {}
        if res.get('result') == 'true':
            lbank_map = {item['symbol'].replace('_usdt', '').upper(): float(item['ticker']['latest']) for item in res['data']}
            for coin in coins:
                prices[coin] = lbank_map.get(coin, 0.0)
        return fx, prices
    except:
        return 1400.0, {coin: 0.0 for coin in coins}

# --- UI 구성 ---
st.set_page_config(page_title="Asset Intelligence", layout="centered")

# --- 쿠키에서 코인 리스트 불러오기 ---
# 쿠키 로딩은 약간의 지연이 있을 수 있으므로 세션 상태와 연동합니다.
saved_coins = controller.get('my_target_coins')
if saved_coins is None:
    # 쿠키가 없으면 기본값 설정
    initial_coins = ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE']
else:
    initial_coins = saved_coins

if 'target_coins' not in st.session_state:
    st.session_state.target_coins = initial_coins

st.title("🌐 Multi-Asset Calc")
st.caption(f"브라우저 쿠키 기반 저장 기능 활성화 | {time.strftime('%H:%M:%S')}")

# 1. 시장 데이터 로드
usd_to_krw, coin_prices = get_market_data(st.session_state.target_coins)
st.metric("실시간 환율 (USD/KRW)", f"₩ {usd_to_krw:,.2f}")

# 2. 계산 기준 설정
st.subheader("계산 기준")
col1, col2 = st.columns([1, 2])
with col1:
    # 코인 리스트가 비어있을 경우를 대비
    options = ["KRW", "USDT"] + st.session_state.target_coins
    base_asset = st.selectbox("기준 자산", options)
with col2:
    default_val = 1000000.0 if base_asset == "KRW" else 1.0
    input_val = st.number_input("금액/수량 입력", min_value=0.0, value=default_val, step=1.0)

# 3. 계산 로직
if base_asset == "KRW":
    base_usdt = input_val / usd_to_krw
elif base_asset == "USDT":
    base_usdt = input_val
else:
    p_usdt = coin_prices.get(base_asset, 0.0)
    base_usdt = input_val * p_usdt if p_usdt > 0 else 0.0

# 4. 결과 테이블 생성
data = [
    ["KRW", f"$ {1/usd_to_krw:,.6f}", "₩ 1.00", f"{base_usdt * usd_to_krw:,.0f}"],
    ["USDT", "$ 1.00", f"₩ {usd_to_krw:,.2f}", f"{base_usdt:,.2f}"]
]

for coin in st.session_state.target_coins:
    p_u = coin_prices.get(coin, 0.0)
    if p_u > 0:
        data.append([coin, f"$ {p_u:,.4f}", f"₩ {p_u * usd_to_krw:,.2f}", f"{base_usdt / p_u:,.6f}"])
    else:
        data.append([coin, "N/A", "N/A", "0.000000"])

df = pd.DataFrame(data, columns=["자산", "시세(USDT)", "시세(KRW)", "보유(계산)수량"])
st.table(df)

# 5. 자산 관리 (쿠키 저장 로직 포함)
with st.expander("⚙️ 자산 관리 (브라우저에 저장됨)"):
    add_col, del_col = st.columns(2)
    
    with add_col:
        new_coin = st.text_input("추가할 코인 심볼").upper().strip()
        if st.button("코인 추가"):
            if new_coin and new_coin not in st.session_state.target_coins:
                st.session_state.target_coins.append(new_coin)
                # 쿠키에 저장 (유효기간 약 1년)
                controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                st.success(f"{new_coin} 추가 완료!")
                time.sleep(1)
                st.rerun()

    with del_col:
        if st.session_state.target_coins:
            del_coin = st.selectbox("삭제할 코인", st.session_state.target_coins)
            if st.button("코인 삭제"):
                st.session_state.target_coins.remove(del_coin)
                # 쿠키 업데이트
                controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                st.warning(f"{del_coin} 삭제 완료!")
                time.sleep(1)
                st.rerun()

st.info("💡 설정은 사용중인 브라우저 쿠키에 보관됩니다. (쿠키 삭제 시 초기화)")