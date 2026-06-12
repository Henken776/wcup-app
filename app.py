import streamlit as st
import pandas as pd

st.set_page_config(page_title="W杯サッカーくじ集計システム", layout="wide")

# スプレッドシートのベースURL
BASE_URL = "https://docs.google.com/spreadsheets/d/1_vlPH_Yl5zYKT4-5p5POZZLM1cJPbYwQ0yzUjF0FinA"

# 【A列・B列完全分離版】A列＝試合結果、B列＝管理人のコメントとして読み込みます
URL_COUNTRIES = f"{BASE_URL}/export?format=csv&gid=0"          # 1番目のシート（48カ国のマスタ勝敗）
URL_SETTINGS = f"{BASE_URL}/export?format=csv&gid=460959744"  # 2番目のシート（設定・コメント）
URL_ODDS = f"{BASE_URL}/export?format=csv&gid=1519733841" # 3番目のシート（オッズ）

@st.cache_data(ttl=300)
def load_data():
    try:
        # 1. 48カ国の勝敗マスタを読み込み
        df_master = pd.read_csv(URL_COUNTRIES)
        for col in ['グループ', '国名', 'オッズ', '勝ち数', '分け数', '負け数']:
            if col not in df_master.columns:
                st.error(f"「シート1」に '{col}' の列が見つかりません。")
                return None, None, None
        
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
            
        # 3. 設定（A列：試合結果 ＆ B列：俺の一言）データを読み込み
        settings = {'results': '', 'my_comment': ''}
        try:
            sett_df = pd.read_csv(URL_SETTINGS)
            if not sett_df.empty:
                # A列（1列目）：試合結果のリスト
                col_results = sett_df.columns[0]
                all_results = "\n".join(sett_df[col_results].dropna().astype(str).tolist())
                settings['results'] = all_results
                
                # B列（2列目）：管理人のコメント（1行目に入っている文字を取得）
                if len(sett_df.columns) >= 2:
                    col_comment = sett_df.columns[1]
                    # B列の空でない最初のデータを取得
                    valid_comments = sett_df[col_comment].dropna().tolist()
                    if valid_comments:
                        settings['my_comment'] = str(valid_comments[0])
        except Exception as e:
            st.error(f"設定シートの読み込みエラー: {e}")
            
        return df_master, df_odds, settings
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        return None, None, None

df_master, df_odds, settings = load_data()

if df_master is None or df_master.empty:
    st.warning("⚠️ スプレッドシートのデータが正しく読み込めませんでした。")
else:
    # 題名
    st.title("🏆 W杯サッカーくじ集計システム")
    st.write("---")
    
    # ==========================================
    # 📢 試合結果 ＆ 今日の勝ち頭（不定期更新）エリア
    # ==========================================
    col_res, col_my = st.columns(2)
    
    with col_res:
        st.subheader("📅 今日の試合結果")
        if settings and settings['results']:
            st.info(settings['results'].replace('\n', '  \n'))
        else:
            st.info("本日の試合結果はまだ登録されていません。")
            
    with col_my:
        st.subheader("🏆 今日の勝ち頭（不定期更新）")
        if settings and settings['my_comment']:
            # B列に書かれたコメントをグリーンの枠に表示
            st.success(settings['my_comment'].replace('\n', '  \n'))
        else:
            st.success("ここに管理人からの熱い戦況コメントや、本日の勝ち頭への煽りが表示されます！")
            
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
