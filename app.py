import streamlit as st
import pandas as pd

st.set_page_config(page_title="W杯ドラフトくじシステム", layout="wide")

# スプレッドシートのベースURL
BASE_URL = "https://docs.google.com/spreadsheets/d/1_vlPH_Yl5zYKT4-5p5POZZLM1cJPbYwQ0yzUjF0FinA"

# 【完全自動連動版】3つのシートを完璧に組み合わせて集計します
URL_COUNTRIES = f"{BASE_URL}/export?format=csv&gid=0"          # 1番目のシート（48カ国のマスタ勝敗）
URL_SETTINGS = f"{BASE_URL}/export?format=csv&gid=460959744"  # 2番目のシート（設定・AIヘンケン）
URL_ODDS = f"{BASE_URL}/export?format=csv&sheet=オッズ"         # 3番目のシート（誰がどの国をオッズしたか）

@st.cache_data(ttl=300)
def load_data():
    try:
        # 1. 48カ国の勝敗マスタを読み込み
        df_master = pd.read_csv(URL_COUNTRIES)
        # 必要な列のチェック
        for col in ['グループ', '国名', 'オッズ', '勝ち数', '分け数', '負け数']:
            if col not in df_master.columns:
                st.error(f"「シート1」に '{col}' の列が見つかりません。")
                return None, None
        
        df_master['勝ち数'] = df_master['勝ち数'].fillna(0).astype(int)
        df_master['分け数'] = df_master['分け数'].fillna(0).astype(int)
        df_master['負け数'] = df_master['負け数'].fillna(0).astype(int)
        df_master['オッズ'] = df_master['オッズ'].fillna(1.0).astype(float)
        
        # 勝ち点と基本ポイントの計算
        df_master['勝ち点'] = df_master['勝ち数'] * 3 + df_master['分け数'] * 1
        df_master['ポイント'] = df_master['オッズ'] * df_master['勝ち点']
        
        # 2. 参加者のオッズデータを読み込み
        try:
            df_odds = pd.read_csv(URL_ODDS)
            df_odds['参加者'] = df_odds['参加者'].fillna('未選択').astype(str).str.strip()
            df_odds['国名'] = df_odds['国名'].astype(str).str.strip()
        except:
            # オッズシートがない、または空の場合はダミーを作成
            df_odds = pd.DataFrame(columns=['参加者', '国名'])
            
        # 3. 設定（試合結果・AIメモ）データを読み込み
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
            
        return df_master, df_odds, settings
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        return None, None, None

df_master, df_odds, settings = load_data()

if df_master is None or df_master.empty:
    st.warning("⚠️ スプレッドシートのデータが正しく読み込めませんでした。")
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
    # 1. 参加者ランキング（マスタとオッズを合体させて計算）
    # ==========================================
    st.header("📊 参加者ランキング")
    
    if not df_odds.empty:
        # オッズデータに、マスタのポイントを国名をキーにしてドッキング（紐付け）
        df_player_points = pd.merge(df_odds, df_master[['国名', 'ポイント']], on='国名', how='left')
        df_player_points['ポイント'] = df_player_points['ポイント'].fillna(0)
        
        # 参加者ごとに合計
        ranking_df = df_player_points.groupby('参加者')['ポイント'].sum().reset_index()
        ranking_df.columns = ['参加者', '総ポイント']
        
        # 実際の参加者だけの平均ポイント
        average_point = ranking_df['総ポイント'].mean()
        
        # 収支ポイントの計算
        ranking_df['収支ポイント'] = ranking_df['総ポイント'] - average_point
        ranking_df = ranking_df.sort_values(by='総ポイント', ascending=False).reset_index(drop=True)
        
        ranking_df['総ポイント'] = ranking_df['総ポイント'].round(1)
        ranking_df['収支ポイント'] = ranking_df['収支ポイント'].round(1)
        
        st.dataframe(ranking_df, use_container_width=True)
        st.caption(f"（※現在の実際の参加者平均ポイント: {average_point:.1f} pt）")
    else:
        st.info("「オッズ」シートに参加者のデータが入力されると、ここにランキングが表示されます。")

    # ==========================================
    # 2. 各国の詳細データ一覧（全48カ国＋オッズした人の一覧）
    # ==========================================
    st.header("⚽ 全48カ国 ステータス一覧")
    
    # 誰がどの国を持っているかを分かりやすく文字で結合（例: あなた, Aさん）
    df_owners = df_odds.groupby('国名')['参加者'].apply(lambda x: ', '.join(x)).reset_index()
    df_owners.columns = ['国名', 'オッズした人']
    
    # 48カ国のマスタに、オッズした人の名前をドッキング
    df_final_show = pd.merge(df_master, df_owners, on='国名', how='left')
    df_final_show['オッズした人'] = df_final_show['オッズした人'].fillna('—（未選択）')
    
    # 画面に表示する列を整理
    show_df = df_final_show[['グループ', '国名', 'オッズ', '勝ち数', '分け数', '負け数', '勝ち点', 'ポイント', 'オッズした人']]
    
    st.dataframe(show_df.sort_values(by=['グループ', '国名']), use_container_width=True, hide_index=True)
