import streamlit as st
import pandas as pd

st.set_page_config(page_title="W杯サッカーくじ集計システム", layout="wide")

# スプレッドシートのベースURL
BASE_URL = "https://docs.google.com/spreadsheets/d/1_vlPH_Yl5zYKT4-5p5POZZLM1cJPbYwQ0yzUjF0FinA"

# 【当日ポイント勝ち頭完全対応版】
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
            
        # 3. 設定（A列：試合結果日付 ＆ B列：コメント）データを読み込み
        settings = {'results_raw': '', 'my_comment': ''}
        today_countries = []
        target_date = ""
        
        try:
            sett_df = pd.read_csv(URL_SETTINGS)
            if not sett_df.empty:
                col_results = sett_df.columns[0]
                raw_lines = sett_df[col_results].dropna().astype(str).tolist()
                settings['results_raw'] = "\n".join(raw_lines)
                
                # 日付データの解析 (例: "6/19, 韓国")
                parsed_games = []
                for line in raw_lines:
                    if ',' in line:
                        parts = line.split(',', 1)
                        dt = parts[0].strip()
                        c_name = parts[1].strip()
                        parsed_games.append({'date': dt, '国名': c_name})
                
                if parsed_games:
                    df_parsed = pd.DataFrame(parsed_games)
                    # 最下行の日付を「当日」とする
                    target_date = df_parsed.iloc[-1]['date']
                    today_countries = df_parsed[df_parsed['date'] == target_date]['国名'].tolist()
                
                # B列：管理人のコメントをすべて結合
                if len(sett_df.columns) >= 2:
                    col_comment = sett_df.columns[1]
                    all_comments = sett_df[col_comment].dropna().astype(str).tolist()
                    if all_comments:
                        settings['my_comment'] = "\n\n".join(all_comments)
        except Exception as e:
            st.error(f"設定シートの読み込みエラー: {e}")
            
        return df_master, df_odds, settings, today_countries, target_date
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        return None, None, None, None, None

df_master, df_odds, settings, today_countries, target_date = load_data()

if df_master is None or df_master.empty:
    st.warning("⚠️ スプレッドシートのデータが正しく読み込めませんでした。")
else:
    st.title("🏆 W杯サッカーくじ集計システム")
    st.write("---")
    
    # ==========================================
    # 📢 試合結果 ＆ 今日のポイント勝ち頭表示エリア
    # ==========================================
    col_res, col_my = st.columns(2)
    
    with col_res:
        st.subheader("📅 本日の対象国")
        if target_date and today_countries:
            st.info(f"**【本日 {target_date} の集計対象】** \n" + "、".join(today_countries))
        elif settings['results_raw']:
            st.info(settings['results_raw'].replace('\n', '  \n'))
        else:
            st.info("本日の対象国はまだ登録されていません。")
            
    with col_my:
        # 当日の対象国データから「本日最もポイントを稼いだ人」を算出
        calculated_header = "🏆 今日の勝ち頭（不定期更新）"
        
        if today_countries and not df_odds.empty:
            # 本日の対象国のポイントデータを抽出
            df_today_master = df_master[df_master['国名'].isin(today_countries)].copy()
            df_today_player = pd.merge(df_odds, df_today_master[['国名', 'ポイント']], on='国名', how='inner')
            
            if not df_today_player.empty:
                # 参加者ごとに、本日対象国の総ポイントを合計
                today_ranking = df_today_player.groupby('参加者')['ポイント'].sum().reset_index()
                today_ranking = today_ranking.sort_values(by='ポイント', ascending=False).reset_index(drop=True)
                
                top_player = today_ranking.iloc[0]['参加者']
                top_pt = today_ranking.iloc[0]['ポイント']
                # タイトルを「本日のポイント勝ち頭」に自動書き換え
                calculated_header = f"👑 本日のポイント勝ち頭: {top_player} さん (+{top_pt:.1f} pt)"

        st.subheader(calculated_header)
        if settings and settings['my_comment']:
            st.success(settings['my_comment'].replace('\n', '  \n'))
        else:
            st.success("ここに管理人からのコメントが表示されます。")
            
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
