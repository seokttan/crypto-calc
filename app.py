import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from streamlit_cookies_controller import CookieController
from curl_cffi import requests as requests_cffi

# --- [1] 초기 설정 ---
st.set_page_config(page_title="Real-time Asset Sync", layout="wide")
controller = CookieController()

# 관리자 비밀번호 설정 (원하는 비밀번호로 수정하세요)
ADMIN_PASSWORD = "1234"

@st.cache_data(ttl=60)
def get_exchange_rate():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/USDKRW=X?interval=1m&range=1d"
        r = requests_cffi.Session(impersonate="chrome").get(url, timeout=5)
        data = r.json()
        price = data['chart']['result'][0]['meta']['regularMarketPrice']
        return float(price)
    except:
        return 1450.0

def get_lbank_prices(coins):
    try:
        res = requests.get("https://api.lbkex.com/v2/ticker/24hr.do", params={'symbol': 'all'}, timeout=3).json()
        if res.get('result') == 'true':
            lbank_map = {item['symbol'].replace('_usdt', '').upper(): float(item['ticker']['latest']) for item in res['data']}
            return {coin: lbank_map.get(coin, 0.0) for coin in coins}
        return {coin: 0.0 for coin in coins}
    except:
        return {coin: 0.0 for coin in coins}

# 숫자를 깔끔하게 포맷팅하는 함수
def format_num(val, precision=6):
    if val == 0: return "0"
    return f"{val:,.{precision}f}".rstrip('0').rstrip('.')

# --- [2] 데이터 로드 (쿠키 및 세션) ---
if 'target_coins' not in st.session_state:
    saved_coins = controller.get('my_target_coins')
    st.session_state.target_coins = saved_coins if saved_coins else ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE']

# --- [3] 상단 고정 레이아웃 (입력창) ---
with st.container():
    st.subheader("계산 기준 설정")
    c1, c2 = st.columns([1, 2])
    with c1:
        options = ["KRW", "USDT"] + st.session_state.target_coins
        base_asset = st.selectbox("보유 중인 기준 자산", options)
    with c2:
        default_val = 1000000.0 if base_asset == "KRW" else 1.0
        input_val = st.number_input(f"{base_asset} 수량/금액 입력", min_value=0.0, value=default_val, step=0.1, format="%g")

st.divider()

# --- [4] 결과 영역 확보 ---
result_area = st.empty()
st.write("") 
st.divider()

# --- [5] 하단 도구: 간편 계산기 & 편집창 (비밀번호 보호) ---
col_calc, col_edit = st.columns(2)

with col_calc:
    with st.expander("🧮 간편 계산기", expanded=False):
        calc_n1 = st.number_input("숫자 1", value=0.0, format="%g", key="n1")
        calc_n2 = st.number_input("숫자 2", value=0.0, format="%g", key="n2")
        op = st.radio("연산", ["+", "-", "×", "÷"], horizontal=True)
        
        res = 0.0
        if op == "+": res = calc_n1 + calc_n2
        elif op == "-": res = calc_n1 - calc_n2
        elif op == "×": res = calc_n1 * calc_n2
        elif op == "÷": res = calc_n1 / calc_n2 if calc_n2 != 0 else 0
        
        st.info(f"결과: {format_num(res)}")

with col_edit:
    with st.expander("⚙️ 내 자산 리스트 편집", expanded=False):
        # 비밀번호 입력 확인
        input_pw = st.text_input("관리자 비밀번호", type="password", placeholder="비밀번호를 입력하세요")
        
        if input_pw == ADMIN_PASSWORD:
            st.success("인증 완료: 자산을 편집할 수 있습니다.")
            add_col, del_col = st.columns(2)
            
            with add_col:
                new_coin = st.text_input("추가할 코인 심볼", key="input_new", placeholder="예: PEPE").upper().strip()
                if st.button("추가", use_container_width=True):
                    if new_coin:
                        check_price = get_lbank_prices([new_coin])
                        if check_price.get(new_coin, 0.0) > 0:
                            if new_coin not in st.session_state.target_coins:
                                st.session_state.target_coins.append(new_coin)
                                controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                                st.rerun()
                            else: st.warning("이미 존재합니다.")
                        else: st.error("LBank에 해당 심볼이 없거나 가격을 불러올 수 없습니다.")
            
            with del_col:
                if st.session_state.target_coins:
                    del_target = st.selectbox("삭제 선택", st.session_state.target_coins)
                    if st.button("삭제", use_container_width=True):
                        st.session_state.target_coins.remove(del_target)
                        controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                        st.rerun()
        elif input_pw != "":
            st.error("비밀번호가 일치하지 않습니다.")
        else:
            st.info("편집하려면 관리자 비밀번호를 입력해 주세요.")

# --- [6] 실시간 업데이트 루프 ---
while True:
    with result_area.container():
        usd_to_krw = get_exchange_rate()
        coin_prices = get_lbank_prices(st.session_state.target_coins)
        kor_now = datetime.utcnow() + timedelta(hours=9)
        
        st.caption(f"Last Update: {kor_now.strftime('%H:%M:%S')}")
        st.metric("현재 환율 (USDKRW)", f"₩ {usd_to_krw:,.2f}")
        
        # 기준 자산을 USDT로 환산
        if base_asset == "KRW":
            base_usdt = input_val / usd_to_krw
        elif base_asset == "USDT":
            base_usdt = input_val
        else:
            p_u = coin_prices.get(base_asset, 0.0)
            base_usdt = input_val * p_u if p_u > 0 else 0.0

        # 데이터프레임 구성
        data = [
            ["🇰🇷 KRW (현금)", f"₩ 1.00", f"₩ {format_num(base_usdt * usd_to_krw, 0)}"],
            ["🇺🇸 USDT (테더)", f"₩ {usd_to_krw:,.2f}", f"{format_num(base_usdt)} USDT"]
        ]
        
        for coin in st.session_state.target_coins:
            p_u = coin_prices.get(coin, 0.0)
            p_k = p_u * usd_to_krw
            qty = base_usdt / p_u if p_u > 0 else 0.0
            
            if p_u > 0:
                data.append([f"🪙 {coin}", f"₩ {p_k:,.2f}", f"{format_num(qty)} {coin}"])

        df = pd.DataFrame(data, columns=["자산명", "개당 시세(KRW)", "환산 수량"])
        st.dataframe(df, use_container_width=True, hide_index=True)

