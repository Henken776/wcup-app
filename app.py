import streamlit as st
import pandas as pd

st.set_page_config(page_title="W杯サッカーくじ集計システム", layout="wide")

# スプレッドシートのベースURL
BASE_URL = "https://docs.google.com/spreadsheets/d/1_vlPH_Yl5zYKT4-5p5POZZLM1cJPbYwQ0yzUjF0FinA"

# 各シートのID（固定）
URL_COUNTRIES = f"{BASE_URL}/export?format=csv&gid=0"          # 1番目のシート（48カ国のマスタ勝敗）
URL_SETTINGS = f"{BASE_URL}/export?format=csv&gid=460959744"  # 2番目のシート（設定・コメント）
URL_ODDS = f"{BASE_URL}/export?format=csv&gid=1519733841"     # 3番目のシート（オッズ）

@st.cache_data(ttl=300)
def load_data():
    try:
        # 1. 48カ国の勝敗マスタを読み込み
        df_master = pd.read_csv(URL_COUNTRIES)
        for col in ['グループ', '国名', 'オッズ', '勝ち数', '分け数', '負け数']:
            if col not in df_master.columns:
                st.error(f"「シート1」に '{col}' の列が見つかりません。")
                return None, None, None, None, None
        
        df_master['勝ち数'] = df_master['勝ち数'].fillna(0).astype(int)
        df_master['分け数'] = df_master['分け数'].fillna(0).astype(int)
        df_master['負け数'] = df_master['負け数'].fillna(0).astype(int)
        df_master['オッズ'] = df_master['オッズ'].fillna(1.0).astype(float)
        
        df_master['勝ち点'] = df_master['勝ち数'] * 3 + df_master['分け数'] * 1
        df_master['ポイント'] = df_master['オッズ'] * df_master['勝ち点']
        
        # 2. 参加者のオッズデータを読み込み
        try:
            df_odds = pd.read_csv(URL_ODDS)
            df_odds['参加者'] = df_odds['参加者'].fillna('未選択').astype(str).str.strip()
            df_odds['国名'] = df_odds['国名'].astype(str).str.strip()
        except:
            df_odds = pd.DataFrame(columns=['参加者', '国名'])
            
        # 3. 設定データの読み込みと全日程の解析
        settings = {'results_raw': '', 'my_comment': ''}
        day_data = {} 
        
        try:
            sett_df = pd.read_csv(URL_SETTINGS)
            if not sett_df.empty:
                col_results = sett_df.columns[0]
                raw_lines = sett_df[col_results].dropna().astype(str).tolist()
                settings['results_raw'] = "\n".join(raw_lines)
                
                for line in raw_lines:
                    if ',' in line:
                        parts = line.split(',', 1)
                        dt = parts[0].strip()
                        c_name = parts[1].strip()
                        
                        if dt not in day_data:
                            day_data[dt] = []
                        if c_name not in day_data[dt]:
                            day_data[dt].append(c_name)
                
                # B列：管理人のコメントをすべて結合
                if len(sett_df.columns) >= 2:
                    col_comment = sett_df.columns[1]
                    all_comments = sett_df[col_comment].dropna().astype(str).tolist()
                    if all_comments:
                        settings['my_comment'] = "\n\n".join(all_comments)
        except Exception as e:
            st.error(f"設定シートの読み込みエラー: {e}")
            
        # 日付文字列を「月/日」の数値ベースでソート
        def parse_date_key(date_str):
            try:
                m, d = map(int, date_str.split('/'))
                return (m, d)
            except:
                return (0, 0)
                
        sorted_dates = sorted(list(day_data.keys()), key=parse_date_key)
            
        return df_master, df_odds, settings, day_data, sorted_dates
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        return None, None, None, None, None

df_master, df_odds, settings, day_data, date_list = load_data()

# 各国のマスタ情報から「1試合あたりのポイント」を安全に割り出す関数
def get_country_daily_point(c_name, df_master_data):
    match_rows = df_master_data[df_master_data['国名'] == c_name]
    if match_rows.empty:
        return 0.0
    row
