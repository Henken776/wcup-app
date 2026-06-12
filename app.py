import streamlit as st
import pandas as pd

st.set_page_config(page_title="W杯サッカーくじ集計システム", layout="wide")

# スプレッドシートのベースURL
BASE_URL = "https://docs.google.com/spreadsheets/d/1_vlPH_Yl5zYKT4-5p5POZZLM1cJPbYwQ0yzUjF0FinA"

# 【バグ修正版】大富豪とドロ沼王の重複を防止するロジックを追加しました
URL_COUNTRIES = f"{BASE_URL}/export?format=csv&gid=0"          # 1番目のシート（48カ国のマスタ勝敗）
URL_SETTINGS = f"{BASE_URL}/export?format=csv&gid=460959744"  # 2番目のシート（設定・AIヘンケン）
URL_ODDS = f"{BASE_URL}/export?format=csv&gid=1519733841" # 3番目のシート（オッズ）

@st.cache_data(ttl=300)
def load_data():
    try:
        # 1. 48カ国の勝敗マスタを読み込み
        df_master = pd.read_csv(URL_COUNTRIES)
        for col in ['グループ', '国名', 'オッズ', '勝ち数', '分け数', '負け数']:
            if col not in df_master.columns:
                st.error(f"「シート1」に '{col}' の列が見つかりません。")
                return None, None, None, None
        
        df_master['勝ち数'] = df_master['勝ち数'].fillna(0).astype(int)
        df_master['分け数'] = df_master['分け数'].fillna(0).astype(int)
        df_master['負け数'] = df_master['負け数'].fillna(0).astype(int)
        df_master['オッズ'] = df_master['オッズ'].fillna(1.0).astype(float)
        
        df_master['勝ち点'] = df_master['勝ち数'] * 3 + df_master['分け数'] * 1
        df_master['ポイント'] = df_master['オッズ'] * df_master['勝ち点']
        
        # 【今日のポイント計算用】「勝ち数」か「分け数」が1以上の国だけを抽出
        df_today_games = df_master[(df_master['勝ち数'] > 0) | (df_master['分け数'] > 0)].copy()
        
        # 2. 参加者のオッズデータを読み込み
        try:
            df_odds = pd.read_csv(URL_ODDS)
            df_odds['参加者'] = df_odds['参加者'].fillna('未選択').astype(str).str.strip()
            df_odds['国名'] = df_odds['国名'].astype(str).str.strip()
        except:
            df_odds = pd.DataFrame(columns=['参加者', '国名'])
            
        # 3. 設定（試合結果）データを読み込み
        try:
            sett_df = pd.read_csv(URL_SETTINGS)
            if not sett_df.empty:
                col_results = sett_df.columns[0]
                all_results = "\n".join(sett_df[col_results].dropna().astype(str).tolist())
                settings = {'results': all_results}
            else:
                settings = {'results': ''}
        except:
            settings = {'results': ''}
            
        return df_master, df_odds, settings, df_today_games
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        return None, None, None, None

df_master, df_odds, settings, df_today_games = load_data()

if df_master is None or df_master.empty:
    st.warning("⚠️ スプレッドシートのデータが正しく読み込めませんでした。")
else:
    # 題名
    st.title("🏆 W杯サッカーくじ集計システム")
    st.write("---")
    
    # ==========================================
    # 📢 試合結果 ＆ AIヘンケン（自動煽り）表示エリア
    # ==========================================
    col_res, col_ai = st.columns(2)
    
    with col_res:
        st.subheader("📅 今日の試合結果")
        if settings and settings['results']:
            st.info(settings['results'].replace('\n', '  \n'))
        else:
            st.info("本日の試合結果はまだ登録されていません。")
            
    with col_ai:
        st.subheader("🤖 AIヘンケン戦況アナリティクス")
        
        if not df_today_games.empty and not df_odds.empty:
            df_today_player = pd.merge(df_odds, df_today_games[['国名', 'ポイント', 'オッズ']], on='国名', how='inner')
            
            if not df_today_player.empty:
                # 参加者ごとに今日稼いだポイントを合計
                today_ranking = df_today_player.groupby('参加者')['ポイント'].sum().reset_index()
                today_ranking = today_ranking.sort_values(by='ポイント', ascending=False).reset_index(drop=True)
                
                # トップの取得
                top_player = today_ranking.iloc[0]['参加者']
                top_pt = today_ranking.iloc[0]['ポイント']
                
                # メッセージの初期化
                ai_comment = f"""👑 **【本日の大富豪（勝ち頭）】** スポットライトは **{top_player}** さん！今日だけで **+{top_pt:.1f} pt** を荒稼ぎしました。  
                「完全に味を占めていますね。今夜は高級なビールでも飲んでいることでしょう。妬ましい！」"""
                
                # 今日動いた人が「2人以上」いて、かつトップとラストの人が違う場合だけドロ沼王を表示
                if len(today_ranking) > 1:
                    worst_player = today_ranking.iloc[-1]['参加者']
                    worst_pt = today_ranking.iloc[-1]['ポイント']
                    
                    if top_player != worst_player:
                        ai_comment += f"""
                        
☠️ **【本日のドロ沼王（不運）】** 逆に、本日一番イマイチだったのは **{worst_player}** さん（本日: {worst_pt:.1f} pt）。  
「大丈夫です、W杯はまだ始まったばかり。…まあ、ここから巻き返せた人がいるかは偏見ですが知りませんけどね！」"""
                
                st.success(ai_comment)
            else:
                st.write("⚽ 「シート1」で本日勝利した国の『勝ち数』が増えると、ここにAIの辛口レビューが出現します！")
        else:
            st.write("⚽ 「シート1」で本日勝利した国の『勝ち数』が増えると、ここにAIの辛口レビューが出現します！")
            
    st.write("---")

    # 1. 参加者ランキング
    st.header("📊 参加者ランキング")
    if not df_odds.empty and len(df_odds) > 0:
        df_player_points = pd.merge(df_odds, df_master[['国名', 'ポイント']], on='国名', how='left')
        df_player_points['ポイント'] = df_player_points['ポイント'].fillna(0)
        
        ranking_df = df_player_points.groupby('参加者')['ポイント'].sum().reset_index()
        ranking_df.columns = ['参加者', '総ポイント']
        
        average_point = ranking_df['総ポイント'].mean()
        ranking_df['収支ポイント'] = ranking_df['総ポイント'] - average_point
        ranking_df = ranking_df.sort_values(by='総ポイント', ascending=False).reset_index(drop=True)
        
        ranking_df['総ポイント'] = ranking_df['総ポイント'].round(1)
        ranking_df['収支ポイント'] = ranking_df['収支ポイント'].round(1)
        
        st.dataframe(ranking_df, use_container_width=True)
        st.caption(f"（※現在の実際の参加者平均ポイント: {average_point:.1f} pt）")
    else:
        st.info("「オッズ」シートに参加者のデータが入力されると、ここにランキングが表示されます。")

    # 2. 各国の詳細データ一覧
    st.header("⚽ 全48カ国 ステータス一覧")
    if not df_odds.empty:
        df_owners = df_odds.groupby('国名')['参加者'].apply(lambda x: ', '.join(x)).reset_index()
        df_owners.columns = ['国名', 'オッズした人']
        df_final_show = pd.merge(df_master, df_owners, on='国名', how='left')
    else:
        df_final_show = df_master.copy()
        df_final_show['オッズした人'] = '—（未選択）'
        
    df_final_show['オッズした人'] = df_final_show['オッズした人'].fillna('—（未選択）')
    show_df = df_final_show[['グループ', '国名', 'オッズ', '勝ち数', '分け数', '負け数', '勝ち点', 'ポイント', 'オッズした人']]
    st.dataframe(show_df.sort_values(by=['グループ', '国名']), use_container_width=True, hide_index=True)
