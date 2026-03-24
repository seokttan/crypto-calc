import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from streamlit_cookies_controller import CookieController
from curl_cffi import requests as requests_cffi

# --- [1] 설정 및 데이터 로직 ---
controller = CookieController()

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/USDKRW=X?interval=1m&range=1d"
        r = requests_cffi.Session(impersonate="chrome").get(url, timeout=5)
        data = r.json()
        return float(data['chart']['result'][0]['meta']['regularMarketPrice'])
    except:
        return 1425.0

def get_lbank_prices(coins):
    try:
        res = requests.get("https://api.lbkex.com/v2/ticker/24hr.do", params={'symbol': 'all'}, timeout=2).json()
        if res.get('result') == 'true':
            lbank_map = {item['symbol'].replace('_usdt', '').upper(): float(item['ticker']['latest']) for item in res['data']}
            return {coin: lbank_map.get(coin, 0.0) for coin in coins}
        return {coin: 0.0 for coin in coins}
    except:
        return {coin: 0.0 for coin in coins}

# --- [2] UI 설정 ---
st.set_page_config(page_title="Flash Calc", layout="centered")

if 'target_coins' not in st.session_state:
    saved_coins = controller.get('my_target_coins')
    st.session_state.target_coins = saved_coins if saved_coins else ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE']

st.title("🌐 Multi-Asset Calc")

# --- [3] 기준 설정 (상단 고정) ---
c1, c2 = st.columns([1, 2])
with c1:
    base_asset = st.selectbox("기준 자산", ["KRW", "USDT"] + st.session_state.target_coins)
with c2:
    input_val = st.number_input("수량/금액 입력", min_value=0.0, value=1000000.0 if base_asset=="KRW" else 1.0)

st.divider()

# --- [4] 실시간 업데이트 영역 (HTML/JS 기반) ---
# 이 부분은 st.empty()를 하나만 써서 HTML 테이블을 통째로 업데이트합니다.
display_area = st.empty()

# --- [5] 자산 리스트 편집 (최하단 고정) ---
def render_footer_editor():
    with st.expander("⚙️ 내 자산 리스트 편집"):
        add_col, del_col = st.columns(2)
        with add_col:
            new_coin = st.text_input("추가할 심볼", key="add_coin").upper().strip()
            if st.button("추가"):
                if new_coin and new_coin not in st.session_state.target_coins:
                    st.session_state.target_coins.append(new_coin)
                    controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                    st.rerun()
        with del_col:
            del_coin = st.selectbox("삭제할 코인", st.session_state.target_coins, key="del_coin")
            if st.button("삭제"):
                st.session_state.target_coins.remove(del_coin)
                controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                st.rerun()

# --- [6] 무한 루프 (HTML 렌더링) ---
while True:
    usd_to_krw = get_exchange_rate()
    coin_prices = get_lbank_prices(st.session_state.target_coins)
    kor_now = (datetime.utcnow() + timedelta(hours=9)).strftime('%H:%M:%S')

    # 계산 로직
    if base_asset == "KRW":
        base_usdt = input_val / usd_to_krw
    elif base_asset == "USDT":
        base_usdt = input_val
    else:
        p_u = coin_prices.get(base_asset, 0.0)
        base_usdt = input_val * p_u if p_u > 0 else 0.0

    # HTML 테이블 생성 (CSS로 깔끔하게 디자인)
    rows_html = f"""
    <tr style="border-bottom: 1px solid #ddd;"><td>KRW</td><td>₩ 1.00</td><td>{base_usdt * usd_to_krw:,.0f}</td></tr>
    <tr style="border-bottom: 1px solid #ddd;"><td>USDT</td><td>₩ {usd_to_krw:,.2f}</td><td>{base_usdt:,.2f}</td></tr>
    """
    for coin in st.session_state.target_coins:
        p_u = coin_prices.get(coin, 0.0)
        qty = base_usdt / p_u if p_u > 0 else 0.0
        rows_html += f"""
        <tr style="border-bottom: 1px solid #ddd;">
            <td>{coin}</td>
            <td>₩ {p_u * usd_to_krw:,.2f}</td>
            <td style="font-weight: bold; color: #007bff;">{qty:,.6f}</td>
        </tr>
        """

    html_content = f"""
    <div style="font-family: sans-serif;">
        <p style="color: gray; font-size: 0.8rem;">KST {kor_now} | 환율 ₩ {usd_to_krw:,.2f}</p>
        <table style="width: 100%; border-collapse: collapse; text-align: left;">
            <thead>
                <tr style="background-color: #f8f9fa; border-bottom: 2px solid #eee;">
                    <th style="padding: 10px;">자산명</th><th style="padding: 10px;">시세(KRW)</th><th style="padding: 10px;">계산수량</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    """
    
    # st.markdown의 unsafe_allow_html을 사용하면 깜빡임 없이 텍스트만 교체됩니다.
    display_area.markdown(html_content, unsafe_allow_html=True)
    
    # 편집창 렌더링 (루프 안에서 매번 그려도 마크다운 아래에 위치함)
    render_footer_editor()
    
    time.sleep(1)
