import streamlit as st
import pandas as pd

st.set_page_config(page_title="W杯ドラフトくじシステム", layout="wide")

# スプレッドシートのURL（21行目）
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_vlPH_Yl5zYKT4-5p5POZZLM1cJPbYwQ0yzUjF0FinA/export?format=csv"

@st.cache_data(ttl=300)
def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        # 必須の入力列があるかチェック
        required_cols = ['グループ', '国名', 'オッズ', '勝ち数', '分け数', '負け数', '参加者']
        for col in required_cols:
            if col not in df.columns:
                st.error(f"スプレッドシートに '{col}' の列が見つかりません。")
                return None
                
        # データのクレンジングと型変換
        df['勝ち数'] = df['勝ち数'].fillna(0).astype(int)
        df['分け数'] = df['分け数'].fillna(0).astype(int)
        df['負け数'] = df['負け数'].fillna(0).astype(int)
        df['オッズ'] = df['オッズ'].fillna(1.0).astype(float)
        
        # 【ご要望の計算式を完全自動化】
        # 1. 勝ち点 ＝ 勝ち数×3 ＋ 分け数×1
        df['勝ち点'] = df['勝ち数'] * 3 + df['分け数'] * 1
        # 2. ポイント ＝ オッズ × 勝ち点
        df['ポイント'] = df['オッズ'] * df['勝ち点']
        
        return df
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        return None

df = load_data()

if df is None or df.empty:
    st.warning("⚠️ スプレッドシートのデータが正しく読み込めませんでした。列名を確認してください。")
else:
    # ==========================================
    # ⚙️ サイドバー：管理人の入力エリア
    # ==========================================
    st.sidebar.header("📝 本日のスタッツ更新")
    st.sidebar.write("ここに当日の結果を入力するとメイン画面に反映されます。")
    
    # 参加者リスト
    members = list(df['参加者'].unique())
    
    st.sidebar.subheader("⚽ ①当日の試合結果")
    match_results = st.sidebar.text_area("本日のスコアなど", placeholder="例：\n日本 2 - 1 ドイツ\nアルゼンチン 1 - 1 ペルー", height=100)
    
    st.sidebar.subheader("🤖 ②AI総評用メモ")
    top_winner = st.sidebar.selectbox("今日の勝ち頭", ["選択してください"] + members)
    points_moved = st.sidebar.text_input("ポイントの増減や総評", placeholder="例：あなたに+24pt、Aさんは足踏み")

    # ==========================================
    # 🏆 メイン画面の表示
    # ==========================================
    st.title("🏆 W杯ドラフトくじ 集計システム")
    
    # 横並びのレイアウト（結果とAIコメントを最上部に）
    col_res, col_ai = st.columns(2)
    
    with col_res:
        if match_results:
            st.subheader("📅 当日の試合結果")
            st.info(match_results)
            
    with col_ai:
        if top_winner != "選択してください":
            st.subheader("🤖 今日の勝ち頭＆AIコメント")
            ai_comment = f"""
            👑 **【本日の勝ち頭】** 本日の主役は **{top_winner}** さん！見事な引きの強さを発揮しています。  
            
            📊 **【戦況アナリティクス】** {points_moved if points_moved else "ゲームが動き、収支ポイントの地殻変動が始まっています！"}
            """
            st.success(ai_comment)
            
    if match_results or top_winner != "選択してください":
        st.write("---")

    # ==========================================
    # 1. 参加者ランキング（収支ポイント対応）
    # ==========================================
    st.header("📊 参加者ランキング")
    
    ranking_df = df.groupby('参加者')['ポイント'].sum().reset_index()
    ranking_df.columns = ['参加者', '総ポイント']
    
    # 全員の平均ポイント
    average_point = ranking_df['総ポイント'].mean()
    
    # 3. 収支ポイント ＝ ポイント ー 全員の平均ポイント
    ranking_df['収支ポイント'] = ranking_df['総ポイント'] - average_point
    
    # 総ポイント順にソート
    ranking_df = ranking_df.sort_values(by='総ポイント', ascending=False).reset_index(drop=True)
    
    # 小数点第1位に丸める
    ranking_df['総ポイント'] = ranking_df['総ポイント'].round(1)
    ranking_df['収支ポイント'] = ranking_df['収支ポイント'].round(1)
    
    st.dataframe(ranking_df, use_container_width=True)
    st.caption(f"（※現在の全員の平均ポイント: {average_point:.1f} pt）")

    # ==========================================
    # 2. 各国の詳細データ一覧（新レイアウト）
    # ==========================================
    st.header("⚽ 各国の詳細ステータス")
    
    # ご要望の列順に綺麗に並び替えて表示
    show_df = df[['グループ', '国名', 'オッズ', '勝ち数', '分け数', '負け数', '勝ち点', 'ポイント', '参加者']]
    
    # 画面用に「収支ポイント」も仮で結合（国ごとの平均からの差ではなく、ランキング側のみで完結させるため、ここは元の指定項目を表示）
    st.dataframe(show_df.sort_values(by=['グループ', '国名']), use_container_width=True, hide_index=True)
