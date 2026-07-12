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
        
        # すべて整数（int）として確実にキャスト
        df_master['勝ち数'] = df_master['勝ち数'].fillna(0).astype(int)
        df_master['分け数'] = df_master['分け数'].fillna(0).astype(int)
        df_master['負け数'] = df_master['負け数'].fillna(0).astype(int)
        df_master['オッズ'] = df_master['オッズ'].fillna(1).astype(int)
        
        df_master['生日付'] = df_master['日付'].fillna('').astype(str).str.strip()
        df_master['is_eliminated'] = df_master['生日付'].apply(lambda x: '×' in x or 'X' in x.upper())
        
        df_master['勝ち点'] = df_master['勝ち数'] * 3 + df_master['分け数'] * 1
        df_master['ポイント'] = df_master['オッズ'] * df_master['勝ち点']
        df_master['ポイント'] = df_master['ポイント'].astype(int)
        
        # 2. 参加者のオッズデータを読み込み
        try:
            df_odds = pd.read_csv(URL_ODDS)
            df_odds['参加者'] = df_odds['参加者'].fillna('未選択').astype(str).str.strip()
            df_odds['国名'] = df_odds['国名'].astype(str).str.strip()
        except:
            df_odds = pd.DataFrame(columns=['参加者', '国名'])
            
        # 3. 設定データの読み込み
        settings = {'my_comment': ''}
        try:
            sett_df = pd.read_csv(URL_SETTINGS)
            if not sett_df.empty and len(sett_df.columns) >= 2:
                col_comment = sett_df.columns[1]
                all_comments = sett_df[col_comment].dropna().astype(str).tolist()
                if all_comments:
                    settings['my_comment'] = "\n\n".join(all_comments)
        except:
            pass
            
        return df_master, df_odds, settings
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        return None, None, None

df_master, df_odds, settings = load_data()

if df_master is None or df_master.empty:
    st.warning("⚠️ スプレッドシートのデータが正しく読み込めませんでした。")
else:
    st.title("🏆 W杯サッカーくじ集計システム")
    
    if st.button("🔄 最新データに更新する", type="primary"):
        st.cache_data.clear()
        st.rerun()
        
    st.write("---")
    
    # コメント欄
    if settings and settings['my_comment']:
        st.success(settings['my_comment'].replace('\n', '  \n'))
        st.write("---")

    # ==========================================
    # 1. 参加者ランキング
    # ==========================================
    st.header("📊 参加者ランキング")
    if not df_odds.empty and len(df_odds) > 0:
        df_player_points = pd.merge(df_odds, df_master[['国名', 'ポイント']], on='国名', how='left')
        df_player_points['ポイント'] = df_player_points['ポイント'].fillna(0).astype(int)
        
        ranking_df = df_player_points.groupby('参加者')['ポイント'].sum().reset_index()
        ranking_df.columns = ['参加者', '総ポイント']
        
        average_point = ranking_df['総ポイント'].mean()
        ranking_df['収支ポイント'] = ranking_df['総ポイント'] - average_point
        ranking_df['収支ポイント'] = ranking_df['収支ポイント'].round(1)
        
        ranking_df = ranking_df.sort_values(by='総ポイント', ascending=False).reset_index(drop=True)
        st.dataframe(ranking_df, use_container_width=True)
    else:
        st.info("データがありません。")

    # ==========================================
    # 2. 各国の詳細
    # ==========================================
    st.header("⚽ 全48カ国 ステータス一覧")
    if not df_odds.empty:
        df_owners = df_odds.groupby('国名')['参加者'].apply(lambda x: ', '.join(x)).reset_index()
        df_owners.columns = ['国名', 'オッズした人']
        df_final_show = pd.merge(df_master, df_owners, on='国名', how='left')
    else:
        df_final_show = df_master.copy()
        df_final_show['オッズした人'] = '—'
        
    show_df = df_final_show[['グループ', '国名', 'ポイント', 'オッズした人', 'オッズ', '勝ち数', '分け数', '負け数', '日付', '勝ち点']]
    show_df = show_df.sort_values(by=['グループ', '国名']).reset_index(drop=True)
    
    st.dataframe(show_df, use_container_width=True, hide_index=True)
