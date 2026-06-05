import streamlit as st
import pandas as pd

st.set_page_config(page_title="W杯ドラフトくじシステム", layout="wide")

# スプレッドシートのベースURL
BASE_URL = "https://docs.google.com/spreadsheets/d/1_vlPH_Yl5zYKT4-5p5POZZLM1cJPbYwQ0yzUjF0FinA"

# 【確定版】あなたの本物のgid番号を使って、2つのシートを完璧に狙い撃ちします
URL_COUNTRIES = f"{BASE_URL}/export?format=csv&gid=0"          # 1番目のシート（国のリスト）
URL_SETTINGS = f"{BASE_URL}/export?format=csv&gid=460959744"  # 2番目のシート（設定）

@st.cache_data(ttl=300)
def load_data():
    try:
        # 1. 国の一覧データを読み込み
        df = pd.read_csv(URL_COUNTRIES)
        required_cols = ['グループ', '国名', 'オッズ', '勝ち数', '分け数', '負け数', '参加者']
        for col in required_cols:
            if col not in df.columns:
                st.error(f"スプレッドシートに '{col}' の列が見つかりません。")
                return None, None
                
        df['勝ち数'] = df['勝ち数'].fillna(0).astype(int)
        df['分け数'] = df['分け数'].fillna(0).astype(int)
        df['負け数'] = df['負け数'].fillna(0).astype(int)
        df['オッズ'] = df['オッズ'].fillna(1.0).astype(float)
        
        # 計算式
        df['勝ち点'] = df['勝ち数'] * 3 + df['分け数'] * 1
        df['ポイント'] = df['オッズ'] * df['勝ち点']
        
        # 2. 設定（試合結果・AIメモ）データを読み込み
        try:
            sett_df = pd.read_csv(URL_SETTINGS)
            if not sett_df.empty:
                col_results = sett_df.columns[0]
                col_winner = sett_df.columns[1] if len(sett_df.columns) > 1 else None
                col_comment = sett_df.columns[2] if len(sett_df.columns) > 2 else None
                
                settings = {
                    'results': sett_df[col_results].fillna('').iloc[0] if col_results else '',
                    'winner': sett_df[col_winner].fillna('').iloc[0] if col_winner else '',
                    'comment': sett_df[col_comment].fillna('').iloc[0] if col_comment else ''
                }
            else:
                settings = {'results': '', 'winner': '', 'comment': ''}
        except:
            settings = {'results': '', 'winner': '', 'comment': ''}
            
        return df, settings
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        return None, None

df, settings = load_data()

if df is None or df.empty:
    st.warning("⚠️ スプレッドシートのデータが正しく読み込めませんでした。シートの列名（グループ、国名など）を確認してください。")
else:
    st.title("🏆 W杯ドラフトくじ 集計システム")
    
    # ==========================================
    # 📢 試合結果 ＆ AIヘンケンの一言 表示エリア
    # ==========================================
    if settings and (settings['results'] or settings['winner']):
        col_res, col_ai = st.columns(2)
        
        with col_res:
            if settings['results']:
                st.subheader("📅 今日の試合結果")
                st.info(str(settings['results']).replace('\n', '  \n'))
                
        with col_ai:
            if settings['winner']:
                st.subheader("🤖 AIヘンケンの一言")
                ai_comment = f"""
                👑 **【本日の勝ち頭】** 今回のスポットライトは **{settings['winner']}** さん！見事な勝負勘を発揮しています。  
                
                📊 **【ヘンケン戦況アナリティクス】** {settings['comment'] if settings['comment'] else "各国の勝敗が動き、収支ポイントの地殻変動が始まっています！"}
                """
                st.success(ai_comment)
                
        st.write("---")

    # ==========================================
    # 1. 参加者ランキング
    # ==========================================
    st.header("📊 参加者ランキング")
    
    ranking_df = df.groupby('参加者')['ポイント'].sum().reset_index()
    ranking_df.columns = ['参加者', '総ポイント']
    
    average_point = ranking_df['総ポイント'].mean()
    ranking_df['収支ポイント'] = ranking_df['総ポイント'] - average_point
    ranking_df = ranking_df.sort_values(by='総ポイント', ascending=False).reset_index(drop=True)
    
    ranking_df['総ポイント'] = ranking_df['総ポイント'].round(1)
    ranking_df['収支ポイント'] = ranking_df['収支ポイント'].round(1)
    
    st.dataframe(ranking_df, use_container_width=True)
    st.caption(f"（※現在の全員の平均ポイント: {average_point:.1f} pt）")

    # ==========================================
    # 2. 各国の詳細データ一覧
    # ==========================================
    st.header("⚽ 各国の詳細ステータス")
    show_df = df[['グループ', '国名', 'オッズ', '勝ち数', '分け数', '負け数', '勝ち点', 'ポイント', '参加者']]
    st.dataframe(show_df.sort_values(by=['グループ', '国名']), use_container_width=True, hide_index=True)
